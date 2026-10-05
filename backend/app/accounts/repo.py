"""Typed queries over the accounts database. Content is encrypted here: callers pass plaintext and the DEK, and only
ciphertext reaches SQLite (the "no plaintext" test scans the file and WAL for that)."""

import json
import sqlite3
from dataclasses import dataclass

from backend.app.accounts.crypto import decrypt_field, encrypt_field, field_aad


@dataclass(frozen=True)
class UserRow:
    """One users row (key material included; never leaves the accounts package)."""

    id: str
    username: str
    display_name: str
    pw_hash: str
    kek_salt: bytes
    dek_pw: bytes
    rc_salt: bytes
    dek_rc: bytes
    prefs_json: str
    created_at: str
    failed_logins: int
    locked_until: float


@dataclass(frozen=True)
class KeyMaterial:
    """Password hash plus both wrapped copies of the DEK and their salts."""

    pw_hash: str
    kek_salt: bytes
    dek_pw: bytes
    rc_salt: bytes
    dek_rc: bytes


def _user(row: sqlite3.Row | None) -> UserRow | None:
    return UserRow(**dict(row)) if row is not None else None


def insert_user(
    conn: sqlite3.Connection, user_id: str, username: str, display_name: str, keys: KeyMaterial, prefs: str, now: str
) -> None:
    """A new user (username already casefolded and checked for uniqueness by the caller's transaction)."""
    conn.execute(
        "INSERT INTO users (id, username, display_name, pw_hash, kek_salt, dek_pw, rc_salt, dek_rc, prefs_json, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            username,
            display_name,
            keys.pw_hash,
            keys.kek_salt,
            keys.dek_pw,
            keys.rc_salt,
            keys.dek_rc,
            prefs,
            now,
        ),
    )


def user_by_username(conn: sqlite3.Connection, username: str) -> UserRow | None:
    """The user with this (casefolded) username."""
    return _user(conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone())


def user_by_id(conn: sqlite3.Connection, user_id: str) -> UserRow | None:
    """The user with this id."""
    return _user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def set_login_state(conn: sqlite3.Connection, user_id: str, failed_logins: int, locked_until: float) -> None:
    """Failed-attempt counter and lockout end."""
    conn.execute(
        "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?", (failed_logins, locked_until, user_id)
    )


def set_keys(conn: sqlite3.Connection, user_id: str, keys: KeyMaterial) -> None:
    """Replace the password hash and wrapped DEKs (password change, recovery); also clears the lockout."""
    conn.execute(
        "UPDATE users SET pw_hash = ?, kek_salt = ?, dek_pw = ?, rc_salt = ?, dek_rc = ?, failed_logins = 0, "
        "locked_until = 0 WHERE id = ?",
        (keys.pw_hash, keys.kek_salt, keys.dek_pw, keys.rc_salt, keys.dek_rc, user_id),
    )


def set_prefs(conn: sqlite3.Connection, user_id: str, prefs: str) -> None:
    """Replace the preferences JSON."""
    conn.execute("UPDATE users SET prefs_json = ? WHERE id = ?", (prefs, user_id))


def delete_user(conn: sqlite3.Connection, user_id: str) -> None:
    """The user and, by cascade, every row they own."""
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def get_profile(conn: sqlite3.Connection, user_id: str, dek: bytes) -> dict[str, str]:
    """The decrypted letter profile ({} if never saved)."""
    row = conn.execute("SELECT data_ct FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return {}
    data: dict[str, str] = json.loads(decrypt_field(dek, row["data_ct"], field_aad("profiles", "data_ct", user_id)))
    return data


def put_profile(conn: sqlite3.Connection, user_id: str, dek: bytes, profile: dict[str, str]) -> None:
    """Encrypt and store the letter profile."""
    sealed = encrypt_field(dek, json.dumps(profile), field_aad("profiles", "data_ct", user_id))
    conn.execute(
        "INSERT INTO profiles (user_id, data_ct) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET data_ct = excluded.data_ct",
        (user_id, sealed),
    )


def add_token(conn: sqlite3.Connection, token_hash: str, user_id: str, created_at: float, expires_at: float) -> None:
    """Remember a sign-in token (its hash only)."""
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, created_at, expires_at),
    )


def token_owner(conn: sqlite3.Connection, token_hash: str, now: float) -> tuple[str, float] | None:
    """(user_id, expires_at) for a token that has not expired."""
    row = conn.execute(
        "SELECT user_id, expires_at FROM auth_tokens WHERE token_hash = ? AND expires_at > ?", (token_hash, now)
    ).fetchone()
    return (row["user_id"], row["expires_at"]) if row else None


def delete_token(conn: sqlite3.Connection, token_hash: str) -> None:
    """Forget one token (sign-out)."""
    conn.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))


def delete_tokens(conn: sqlite3.Connection, user_id: str, keep: str | None = None) -> None:
    """Forget every token of a user, optionally keeping one (password change keeps the current session)."""
    conn.execute("DELETE FROM auth_tokens WHERE user_id = ? AND token_hash IS NOT ?", (user_id, keep))


def purge_tokens(conn: sqlite3.Connection, now: float) -> int:
    """Drop expired tokens; returns how many."""
    return conn.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (now,)).rowcount
