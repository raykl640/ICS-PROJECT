"""Account operations used by the routes: register, sign in with throttling, lock/unlock, recovery, password change,
profile, preferences, export and delete. Errors are AccountError with a stable code and a generic message."""

import json
import math
import re
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.accounts import repo
from backend.app.accounts.auth import AuthSession, AuthSessions, new_token, token_hash
from backend.app.accounts.crypto import (
    CryptoError,
    KdfParams,
    derive_key,
    hash_password,
    new_key,
    new_recovery_code,
    new_salt,
    normalise_recovery_code,
    unwrap_key,
    verify_password,
    wrap_key,
)
from backend.app.accounts.db import Database
from backend.app.config import Settings
from backend.app.security import strip_invisible

PROFILE_FIELDS = ("name", "address", "phone", "email", "id_number")
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_PASSWORD_MAX = 256
_DISPLAY_MAX = 60
_AUTO_LOCK_MINUTES = (1, 120)
_BAD_LOGIN = "That username and password do not match an account on this computer."


class AccountError(Exception):
    """A refused account operation (status, stable code, safe message, optional Retry-After)."""

    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


@dataclass(frozen=True)
class UserView:
    """What the client may see of a user."""

    id: str
    username: str
    display_name: str


@dataclass(frozen=True)
class Prefs:
    """Non-content preferences (stored in plain JSON)."""

    save_history: bool
    auto_lock_minutes: int


@dataclass(frozen=True)
class SignedIn:
    """A new sign-in: the user, the cookie token and, after register/recover, the recovery code to show once."""

    user: UserView
    token: str
    recovery_code: str | None = None


def _view(user: repo.UserRow) -> UserView:
    return UserView(user.id, user.username, user.display_name)


class Accounts:
    """Account operations over one database; clock is epoch seconds (injected in tests)."""

    def __init__(
        self, settings: Settings, db: Database, sessions: AuthSessions, clock: Callable[[], float] = time.time
    ):
        self.settings = settings
        self.db = db
        self.sessions = sessions
        self.clock = clock
        self.kdf = KdfParams.from_settings(settings)
        # Verified when the username is unknown, so a miss costs the same time as a wrong password.
        self._dummy_hash = hash_password(new_recovery_code(), self.kdf)

    # --- validation ---------------------------------------------------------------------------------------------

    def _username(self, raw: str) -> str:
        name = raw.strip().casefold()
        if not (3 <= len(name) <= self.settings.username_max_chars and _USERNAME.match(name)):
            raise AccountError(
                422,
                "invalid_username",
                f"Usernames are 3 to {self.settings.username_max_chars} letters or digits, and may use . _ or -.",
            )
        return name

    def _password(self, password: str) -> str:
        if not self.settings.password_min_chars <= len(password) <= _PASSWORD_MAX:
            raise AccountError(
                422, "weak_password", f"Use a password of at least {self.settings.password_min_chars} characters."
            )
        return password

    @staticmethod
    def _display_name(raw: str, fallback: str) -> str:
        return " ".join(strip_invisible(raw).split())[:_DISPLAY_MAX] or fallback

    # --- keys ---------------------------------------------------------------------------------------------------

    def _key_material(self, password: str, recovery_code: str, dek: bytes) -> repo.KeyMaterial:
        kek_salt, rc_salt = new_salt(), new_salt()
        return repo.KeyMaterial(
            pw_hash=hash_password(password, self.kdf),
            kek_salt=kek_salt,
            dek_pw=wrap_key(derive_key(password, kek_salt, self.kdf), dek),
            rc_salt=rc_salt,
            dek_rc=wrap_key(derive_key(recovery_code, rc_salt, self.kdf), dek),
        )

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self.clock(), UTC).isoformat(timespec="seconds")

    def _prefs(self, user: repo.UserRow) -> Prefs:
        raw: dict[str, Any] = json.loads(user.prefs_json)
        return Prefs(bool(raw.get("save_history", True)), int(raw.get("auto_lock_minutes", self._default_lock_minutes)))

    @property
    def _default_lock_minutes(self) -> int:
        return max(1, self.settings.auto_lock_s // 60)

    def _sign_in(self, user: repo.UserRow, dek: bytes, recovery_code: str | None = None) -> SignedIn:
        token = new_token()
        now = self.clock()
        expires = now + self.settings.auth_session_ttl_s
        with self.db.write() as conn:
            repo.add_token(conn, token_hash(token), user.id, now, expires)
        self.sessions.open(token_hash(token), user.id, dek, expires, self._prefs(user).auto_lock_minutes * 60)
        return SignedIn(_view(user), token, recovery_code)

    # --- throttled secret checks --------------------------------------------------------------------------------

    def _check_secret(self, user: repo.UserRow, ok: Callable[[], bool]) -> None:
        """Run a password/recovery check under the lockout rule; a failure counts towards it."""
        now = self.clock()
        if user.locked_until > now:
            wait = math.ceil(user.locked_until - now)
            raise AccountError(429, "locked_out", "Too many failed attempts. Please wait and try again.", wait)
        if ok():
            if user.failed_logins:
                with self.db.write() as conn:
                    repo.set_login_state(conn, user.id, 0, 0)
            return
        failed = user.failed_logins + 1
        locked_until = 0.0
        over = failed - self.settings.login_max_attempts
        if over >= 0:
            locked_until = now + min(self.settings.login_lockout_s * 2**over, self.settings.login_lockout_max_s)
        with self.db.write() as conn:
            repo.set_login_state(conn, user.id, failed, locked_until)
        raise AccountError(401, "invalid_credentials", _BAD_LOGIN)

    def _unwrap_with_password(self, user: repo.UserRow, password: str) -> bytes:
        dek: list[bytes] = []

        def ok() -> bool:
            if not verify_password(user.pw_hash, password, self.kdf):
                return False
            dek.append(unwrap_key(derive_key(password, user.kek_salt, self.kdf), user.dek_pw))
            return True

        self._check_secret(user, ok)
        return dek[0]

    def _user(self, user_id: str) -> repo.UserRow:
        with self.db.read() as conn:
            user = repo.user_by_id(conn, user_id)
        if user is None:
            raise AccountError(401, "auth_required", "Please sign in.")
        return user

    # --- auth operations ----------------------------------------------------------------------------------------

    def register(self, username: str, password: str, display_name: str) -> SignedIn:
        """A new account, signed in and unlocked, with its recovery code (to show once)."""
        name = self._username(username)
        self._password(password)
        code = new_recovery_code()
        dek = new_key()
        keys = self._key_material(password, code, dek)
        prefs = json.dumps(asdict(Prefs(True, self._default_lock_minutes)))
        user_id = str(uuid.uuid4())
        try:
            with self.db.write() as conn:
                repo.insert_user(
                    conn, user_id, name, self._display_name(display_name, name), keys, prefs, self._now_iso()
                )
        except sqlite3.IntegrityError as exc:
            raise AccountError(409, "username_taken", "That username is already used on this computer.") from exc
        return self._sign_in(self._user(user_id), dek, code)

    def login(self, username: str, password: str) -> SignedIn:
        """Sign in (unlocked); unknown users and wrong passwords get the same answer."""
        with self.db.read() as conn:
            user = repo.user_by_username(conn, username.strip().casefold())
        if user is None:
            verify_password(self._dummy_hash, password, self.kdf)
            raise AccountError(401, "invalid_credentials", _BAD_LOGIN)
        return self._sign_in(user, self._unwrap_with_password(user, password))

    def session(self, token: str | None) -> AuthSession | None:
        """The live session for a cookie token; a token remembered from before a restart comes back locked."""
        if not token:
            return None
        hashed = token_hash(token)
        session = self.sessions.get(hashed)
        if session is not None:
            return session
        with self.db.read() as conn:
            found = repo.token_owner(conn, hashed, self.clock())
            user = repo.user_by_id(conn, found[0]) if found else None
        if found is None or user is None:
            return None
        return self.sessions.open(hashed, user.id, None, found[1], self._prefs(user).auto_lock_minutes * 60)

    def user(self, session: AuthSession) -> UserView:
        """The signed-in user."""
        return _view(self._user(session.user_id))

    def logout(self, session: AuthSession) -> None:
        """End this sign-in everywhere (memory and database)."""
        self.sessions.drop(session.token_hash)
        with self.db.write() as conn:
            repo.delete_token(conn, session.token_hash)

    def lock(self, session: AuthSession) -> None:
        """Drop the data key; the password unlocks again."""
        session.dek = None

    def unlock(self, session: AuthSession, password: str) -> UserView:
        """Unwrap the data key with the password (throttled like sign-in)."""
        user = self._user(session.user_id)
        self.sessions.unlock(session, self._unwrap_with_password(user, password))
        return _view(user)

    def recover(self, username: str, recovery_code: str, new_password: str) -> SignedIn:
        """Reset the password with the recovery code; all other sign-ins end and a new code is issued."""
        self._password(new_password)
        with self.db.read() as conn:
            user = repo.user_by_username(conn, username.strip().casefold())
        if user is None:
            verify_password(self._dummy_hash, recovery_code, self.kdf)
            raise AccountError(401, "invalid_credentials", "That username and recovery code do not match.")
        code = normalise_recovery_code(recovery_code)
        dek: list[bytes] = []

        def ok() -> bool:
            try:
                dek.append(unwrap_key(derive_key(code, user.rc_salt, self.kdf), user.dek_rc))
            except CryptoError:
                return False
            return True

        try:
            self._check_secret(user, ok)
        except AccountError as exc:
            if exc.code == "invalid_credentials":
                raise AccountError(401, exc.code, "That username and recovery code do not match.") from exc
            raise
        new_code = new_recovery_code()
        with self.db.write() as conn:
            repo.set_keys(conn, user.id, self._key_material(new_password, new_code, dek[0]))
            repo.delete_tokens(conn, user.id)
        self.sessions.drop_user(user.id)
        return self._sign_in(self._user(user.id), dek[0], new_code)

    def change_password(self, session: AuthSession, current: str, new: str) -> None:
        """Re-wrap the data key under a new password (the recovery code stays valid); other sign-ins end."""
        self._password(new)
        user = self._user(session.user_id)
        dek = self._unwrap_with_password(user, current)
        kek_salt = new_salt()
        keys = repo.KeyMaterial(
            pw_hash=hash_password(new, self.kdf),
            kek_salt=kek_salt,
            dek_pw=wrap_key(derive_key(new, kek_salt, self.kdf), dek),
            rc_salt=user.rc_salt,
            dek_rc=user.dek_rc,
        )
        with self.db.write() as conn:
            repo.set_keys(conn, user.id, keys)
            repo.delete_tokens(conn, user.id, keep=session.token_hash)
        self.sessions.drop_user(user.id, keep=session.token_hash)

    # --- account data -------------------------------------------------------------------------------------------

    def profile(self, session: AuthSession, dek: bytes) -> dict[str, str]:
        """The decrypted letter profile, every field present."""
        with self.db.read() as conn:
            stored = repo.get_profile(conn, session.user_id, dek)
        return {field: stored.get(field, "") for field in PROFILE_FIELDS}

    def save_profile(self, session: AuthSession, dek: bytes, profile: dict[str, str]) -> dict[str, str]:
        """Clean, cap and store the letter profile (encrypted)."""
        limit = self.settings.profile_field_max_chars
        clean = {field: " ".join(strip_invisible(profile.get(field, "")).split())[:limit] for field in PROFILE_FIELDS}
        with self.db.write() as conn:
            repo.put_profile(conn, session.user_id, dek, clean)
        return clean

    def prefs(self, session: AuthSession) -> Prefs:
        """The user's preferences."""
        return self._prefs(self._user(session.user_id))

    def save_prefs(self, session: AuthSession, prefs: Prefs) -> Prefs:
        """Store preferences; a new auto-lock time applies to live sign-ins at once."""
        low, high = _AUTO_LOCK_MINUTES
        if not low <= prefs.auto_lock_minutes <= high:
            raise AccountError(422, "invalid_prefs", f"Auto-lock must be {low} to {high} minutes.")
        with self.db.write() as conn:
            repo.set_prefs(conn, session.user_id, json.dumps(asdict(prefs)))
        self.sessions.set_auto_lock(session.user_id, prefs.auto_lock_minutes * 60)
        return prefs

    def export(self, session: AuthSession, dek: bytes) -> dict[str, Any]:
        """Everything stored for the user, decrypted."""
        user = self._user(session.user_id)
        return {
            "exported_at": self._now_iso(),
            "user": {"username": user.username, "display_name": user.display_name, "created_at": user.created_at},
            "prefs": asdict(self._prefs(user)),
            "profile": self.profile(session, dek),
        }

    def delete(self, session: AuthSession, password: str) -> None:
        """Password-confirmed: delete every row of the user, end all sign-ins and compact the file."""
        user = self._user(session.user_id)
        self._unwrap_with_password(user, password)
        with self.db.write() as conn:
            repo.delete_user(conn, user.id)
        self.sessions.drop_user(user.id)
        self.db.compact()

    def purge(self) -> int:
        """Drop expired sign-ins from memory and the database."""
        dropped = self.sessions.purge()
        with self.db.write() as conn:
            repo.purge_tokens(conn, self.clock())
        return dropped
