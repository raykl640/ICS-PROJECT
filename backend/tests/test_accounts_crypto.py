"""Envelope encryption: round trips, wrong keys, tampering and AAD swaps fail; recovery codes."""

import re
import sqlite3
from pathlib import Path

import pytest

from backend.app.accounts.crypto import (
    CryptoError,
    KdfParams,
    decrypt_field,
    derive_key,
    encrypt_field,
    field_aad,
    hash_password,
    new_key,
    new_recovery_code,
    new_salt,
    normalise_recovery_code,
    unwrap_key,
    verify_password,
    wrap_key,
)
from backend.app.accounts.db import Database, migrations
from backend.app.config import Settings

CHEAP = KdfParams(time_cost=1, memory_kib=8, parallelism=1)


def test_password_hash_round_trip_and_mismatch() -> None:
    encoded = hash_password("correct horse battery", CHEAP)
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "correct horse battery", CHEAP)
    assert not verify_password(encoded, "wrong horse battery", CHEAP)
    assert not verify_password("not-a-hash", "correct horse battery", CHEAP)


def test_kdf_params_come_from_settings() -> None:
    params = KdfParams.from_settings(Settings(argon2_time_cost=2, argon2_memory_kib=16, argon2_parallelism=1))
    assert params == KdfParams(2, 16, 1)


def test_key_derivation_is_deterministic_per_salt() -> None:
    salt = new_salt()
    assert derive_key("pw", salt, CHEAP) == derive_key("pw", salt, CHEAP)
    assert derive_key("pw", salt, CHEAP) != derive_key("pw", new_salt(), CHEAP)
    assert len(derive_key("pw", salt, CHEAP)) == 32


def test_wrapped_dek_opens_only_with_the_right_key() -> None:
    dek, kek = new_key(), derive_key("password", new_salt(), CHEAP)
    wrapped = wrap_key(kek, dek)
    assert unwrap_key(kek, wrapped) == dek
    with pytest.raises(CryptoError):
        unwrap_key(derive_key("other", new_salt(), CHEAP), wrapped)
    with pytest.raises(CryptoError):
        unwrap_key(kek, wrapped[:-1] + bytes([wrapped[-1] ^ 1]))


def test_field_round_trip_and_every_kind_of_tampering_fails() -> None:
    dek = new_key()
    aad = field_aad("profiles", "data_ct", "user-1")
    sealed = encrypt_field(dek, "Wanjiku Kamau", aad)
    assert b"Wanjiku" not in sealed
    assert decrypt_field(dek, sealed, aad) == "Wanjiku Kamau"
    assert encrypt_field(dek, "Wanjiku Kamau", aad) != sealed  # fresh nonce every time
    with pytest.raises(CryptoError):
        decrypt_field(new_key(), sealed, aad)
    with pytest.raises(CryptoError):
        decrypt_field(dek, sealed[:20] + bytes([sealed[20] ^ 0x80]) + sealed[21:], aad)
    with pytest.raises(CryptoError):  # copied to another user's row
        decrypt_field(dek, sealed, field_aad("profiles", "data_ct", "user-2"))
    with pytest.raises(CryptoError):  # copied to another column
        decrypt_field(dek, sealed, field_aad("profiles", "other_ct", "user-1"))
    with pytest.raises(CryptoError):
        decrypt_field(dek, b"short", aad)


def test_recovery_codes_are_grouped_base32_and_normalise() -> None:
    code = new_recovery_code()
    assert re.fullmatch(r"[A-Z2-7]{4}(-[A-Z2-7]{4}){4}", code)
    assert new_recovery_code() != code
    assert normalise_recovery_code(code.lower().replace("-", " ")) == code


def test_migrations_apply_once_and_set_user_version(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    assert db.version == len(migrations()) >= 1
    Database(tmp_path / "app.db")  # reopening does not re-run them
    with db.read() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "profiles", "auth_tokens"} <= tables


def test_migration_numbering_and_failed_migration_rolls_back(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "001_ok.sql").write_text("CREATE TABLE a (x);")
    (bad / "003_gap.sql").write_text("CREATE TABLE b (x);")
    with pytest.raises(RuntimeError, match="without gaps"):
        migrations(bad)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "001_ok.sql").write_text("CREATE TABLE a (x);")
    (broken / "002_broken.sql").write_text("CREATE TABLE b (x); THIS IS NOT SQL;")
    with pytest.raises(sqlite3.Error):
        Database(tmp_path / "x.db", broken)
    conn = sqlite3.connect(tmp_path / "x.db")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name = 'b'").fetchone()[0] == 0


def test_write_rolls_back_on_error(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    with pytest.raises(ZeroDivisionError), db.write() as conn:
        conn.execute("INSERT INTO users VALUES ('u', 'name', 'Name', 'h', x'00', x'00', x'00', x'00', '{}', 't', 0, 0)")
        raise ZeroDivisionError
    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError), db.write() as conn:  # foreign keys are enforced
        conn.execute("INSERT INTO auth_tokens VALUES ('h', 'nobody', 0, 1)")
