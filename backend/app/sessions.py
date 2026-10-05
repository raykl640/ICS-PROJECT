"""In-memory session store (ARCHITECTURE §8): UUID keys, absolute TTL, size cap that never drops a running session."""

import time
import uuid
from collections.abc import Callable

from backend.app.models import SessionData, SessionStatus

_EVICTION_ORDER: tuple[tuple[SessionStatus, ...], ...] = (("done", "aborted", "error"), ("pending",))


class SessionsFull(RuntimeError):
    """Every session slot holds a running generation."""


class SessionStore:
    """Dict of session_id -> (created, SessionData); insertion order is age order."""

    def __init__(self, ttl_s: float, max_sessions: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl_s = ttl_s
        self._max = max_sessions
        self._clock = clock
        self._items: dict[str, tuple[float, SessionData]] = {}

    def __len__(self) -> int:
        return len(self._items)

    def _expired(self, created: float, data: SessionData, now: float) -> bool:
        """Past its TTL and not generating right now."""
        return now - created > self._ttl_s and data.status != "running"

    def create(self, data: SessionData) -> str:
        """Store data under a new id, purging expired sessions and evicting the oldest finished one when full."""
        self.purge()
        if len(self._items) >= self._max:
            self._evict()
        session_id = uuid.uuid4().hex
        self._items[session_id] = (self._clock(), data)
        return session_id

    def get(self, session_id: str) -> SessionData | None:
        """The live session, or None if unknown or expired (an expired one is dropped)."""
        item = self._items.get(session_id)
        if item is None:
            return None
        if self._expired(*item, self._clock()):
            del self._items[session_id]
            return None
        return item[1]

    def discard(self, session_id: str) -> None:
        """Forget a session (a query that could not start)."""
        self._items.pop(session_id, None)

    def live(self) -> list[tuple[str, SessionData]]:
        """(id, session) of every unexpired session, oldest first."""
        now = self._clock()
        return [(sid, data) for sid, (created, data) in self._items.items() if not self._expired(created, data, now)]

    def purge(self) -> int:
        """Drop every expired session; returns how many were dropped."""
        now = self._clock()
        expired = [sid for sid, item in self._items.items() if self._expired(*item, now)]
        for session_id in expired:
            del self._items[session_id]
        return len(expired)

    def _evict(self) -> None:
        """Drop the oldest finished session, else the oldest never-streamed one; running ones are never dropped."""
        for statuses in _EVICTION_ORDER:
            victim = next((sid for sid, (_, data) in self._items.items() if data.status in statuses), None)
            if victim is not None:
                del self._items[victim]
                return
        raise SessionsFull(f"all {self._max} sessions are generating")
