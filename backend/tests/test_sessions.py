"""SessionStore: TTL expiry, purge, cap with eviction of the oldest finished session; running sessions are kept."""

import pytest

from backend.app.models import SessionData, SessionStatus
from backend.app.sessions import SessionsFull, SessionStore
from backend.tests.api_support import FakeClock


def _session(status: SessionStatus = "pending") -> SessionData:
    return SessionData(question="q", question_en="q", lang="en", chunks=[], fallback=False, status=status)


def test_create_and_get_until_expiry() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_s=60, max_sessions=10, clock=clock)
    sid = store.create(_session())
    assert store.get(sid) is not None
    assert store.get("unknown") is None
    clock.now += 60
    assert store.get(sid) is not None
    clock.now += 1
    assert store.get(sid) is None
    assert len(store) == 0


def test_purge_drops_expired_but_keeps_running_sessions() -> None:
    clock = FakeClock()
    store = SessionStore(ttl_s=10, max_sessions=10, clock=clock)
    done, running = store.create(_session("done")), store.create(_session("running"))
    clock.now += 11
    fresh = store.create(_session())
    assert store.purge() == 0  # create already purged the expired finished session
    assert store.get(done) is None
    assert store.get(running) is not None
    assert store.get(fresh) is not None


def test_cap_evicts_oldest_finished_then_oldest_pending() -> None:
    store = SessionStore(ttl_s=100, max_sessions=3, clock=FakeClock())
    pending = store.create(_session("pending"))
    running = store.create(_session("running"))
    aborted = store.create(_session("aborted"))
    newest = store.create(_session())
    assert store.get(aborted) is None
    assert store.get(pending) is not None
    store.create(_session())
    assert store.get(pending) is None
    assert {store.get(running) is not None, store.get(newest) is not None} == {True}


def test_cap_with_only_running_sessions_raises() -> None:
    store = SessionStore(ttl_s=100, max_sessions=1, clock=FakeClock())
    store.create(_session("running"))
    with pytest.raises(SessionsFull):
        store.create(_session())


def test_session_ids_are_unique_hex() -> None:
    store = SessionStore(ttl_s=100, max_sessions=10, clock=FakeClock())
    ids = {store.create(_session()) for _ in range(5)}
    assert len(ids) == 5
    assert all(len(sid) == 32 and int(sid, 16) >= 0 for sid in ids)
