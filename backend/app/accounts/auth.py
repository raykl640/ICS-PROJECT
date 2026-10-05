"""Signed-in sessions held in server memory: token hash → user, unlocked DEK, last activity.

The DEK exists only here. Sign-out, lock, idle longer than the user's auto-lock time, expiry or a restart drop it; the
token itself is also stored (hashed) in SQLite, so after a restart the same sign-in comes back locked, not forgotten.
"""

import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

TOKEN_BYTES = 32


def new_token() -> str:
    """A random 256-bit sign-in token (the cookie value)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    """What is stored and used as the key: sha256 of the token."""
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


@dataclass
class AuthSession:
    """One sign-in; dek is None while locked."""

    token_hash: str
    user_id: str
    dek: bytes | None
    last_seen: float
    expires_at: float
    auto_lock_s: int

    @property
    def locked(self) -> bool:
        """True when the data key has been dropped."""
        return self.dek is None


class AuthSessions:
    """In-memory map of sign-ins; time comes from the injected clock (epoch seconds)."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._sessions: dict[str, AuthSession] = {}

    def open(
        self, token_hash: str, user_id: str, dek: bytes | None, expires_at: float, auto_lock_s: int
    ) -> AuthSession:
        """Register a sign-in (dek None = restored after a restart, locked)."""
        session = AuthSession(token_hash, user_id, dek, self._clock(), expires_at, auto_lock_s)
        self._sessions[token_hash] = session
        return session

    def get(self, token_hash: str) -> AuthSession | None:
        """The live session (None once expired); one idle past its auto-lock time is locked first."""
        session = self._sessions.get(token_hash)
        if session is None:
            return None
        now = self._clock()
        if now >= session.expires_at:
            del self._sessions[token_hash]
            return None
        if now - session.last_seen > session.auto_lock_s:
            session.dek = None
        return session

    def touch(self, session: AuthSession) -> None:
        """Record activity (resets the idle timer)."""
        session.last_seen = self._clock()

    def lock_in(self, session: AuthSession) -> int:
        """Whole seconds until the idle auto-lock (0 when locked)."""
        if session.locked:
            return 0
        return max(0, int(session.auto_lock_s - (self._clock() - session.last_seen)))

    def unlock(self, session: AuthSession, dek: bytes) -> None:
        """Hold the data key again."""
        session.dek = dek
        self.touch(session)

    def drop(self, token_hash: str) -> None:
        """Forget one sign-in."""
        self._sessions.pop(token_hash, None)

    def drop_user(self, user_id: str, keep: str | None = None) -> None:
        """Forget every sign-in of a user, except keep."""
        self._sessions = {h: s for h, s in self._sessions.items() if s.user_id != user_id or h == keep}

    def set_auto_lock(self, user_id: str, seconds: int) -> None:
        """Apply a changed auto-lock time to the user's live sessions."""
        for session in self._sessions.values():
            if session.user_id == user_id:
                session.auto_lock_s = seconds

    def purge(self) -> int:
        """Drop expired sessions and the keys of idle ones; returns how many sessions were dropped."""
        expired = [h for h in list(self._sessions) if self.get(h) is None]
        return len(expired)

    def __len__(self) -> int:
        return len(self._sessions)
