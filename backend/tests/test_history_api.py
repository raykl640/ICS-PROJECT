"""Saved turns, background runs (D24), stop, per-sign-in events and follow-ups (D23) over the real ASGI app."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from backend.app.main import Runtime
from backend.tests.api_support import (
    EN_QUESTION,
    GARBAGE,
    Reply,
    call,
    make_app,
    runtime,
    sign_in,
    sign_up,
    sse_events,
    tokens_text,
    wait_until,
)
from backend.tests.fakes import DEFAULT_SCRIPT, FakeLLM

FOLLOW_UP = "Can my employer also refuse to pay the wages owed?"


def run(app: FastAPI, scenario: Callable[[Runtime], Awaitable[None]]) -> None:
    """Run an async scenario inside the app's lifespan."""

    async def main() -> None:
        async with app.router.lifespan_context(app):
            await scenario(runtime(app))

    asyncio.run(main())


async def ask(app: FastAPI, cookie: str | None, question: str = EN_QUESTION, **extra: Any) -> dict[str, Any]:
    reply = await call(app, "POST", "/api/query", body={"question": question, "language": "en", **extra}, cookie=cookie)
    assert reply.status == 200, reply.text
    body: dict[str, Any] = reply.json()
    return body


async def get(app: FastAPI, path: str, cookie: str | None) -> Reply:
    return await call(app, "GET", path, cookie=cookie)


def status(rt: Runtime, session_id: str) -> str:
    """A live session's status."""
    session = rt.sessions.get(session_id)
    assert session is not None
    return session.status


async def finished(rt: Runtime, session_id: str) -> None:
    """Wait until a background run's task is over (answer saved and sign-in notified)."""
    await wait_until(lambda: session_id not in rt.runs)


def test_guest_question_is_not_saved_and_not_background(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM())

    async def scenario(rt: Runtime) -> None:
        body = await ask(app, None, background=True)
        assert body["conversation_id"] is None
        assert body["background"] is False
        assert rt.runs == {}
        assert rt.library is not None
        with rt.library.db.read() as conn:
            assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0

    run(app, scenario)


def test_signed_in_background_run_survives_disconnect_and_is_saved(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        listener = asyncio.create_task(
            call(app, "GET", "/api/events", cookie=cookie, disconnect_when=lambda b: "turn_done" in b)
        )
        body = await ask(app, cookie)
        assert body["background"] is True
        cid, sid = body["conversation_id"], body["session_id"]
        assert cid
        partial = await call(
            app, "GET", f"/api/stream/{sid}", cookie=cookie, disconnect_when=lambda b: "event: token" in b
        )
        assert tokens_text(sse_events(partial.text)) == DEFAULT_SCRIPT[0]
        assert not llm.cancelled
        assert (await get(app, f"/api/conversations/{cid}", cookie)).json()["running"][0]["session_id"] == sid
        llm.resume.set()
        events = sse_events((await listener).text)
        assert events == [
            ("turn_done", {"session_id": sid, "conversation_id": cid, "turn_id": events[0][1]["turn_id"]})
        ]
        detail = (await get(app, f"/api/conversations/{cid}", cookie)).json()
        assert detail["running"] == []
        assert detail["title"] == EN_QUESTION
        (turn,) = detail["thread"]
        assert turn["id"] == events[0][1]["turn_id"]
        assert turn["question"] == EN_QUESTION
        assert turn["sections"]["steps"] == "1. Write to the other party."
        assert turn["session_id"] == sid
        assert turn["sources"] and turn["sources"][0]["rank"] == 1
        replay = await get(app, f"/api/stream/{sid}", cookie)
        assert tokens_text(sse_events(replay.text)) == "".join(DEFAULT_SCRIPT)
        assert rt.gate.active == 0

    run(app, scenario)


def test_a_second_connection_follows_a_running_background_answer(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=2)
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        sid = (await ask(app, cookie))["session_id"]
        await wait_until(lambda: len(llm.prompts) == 1)
        first = asyncio.create_task(get(app, f"/api/stream/{sid}", cookie))
        second = asyncio.create_task(get(app, f"/api/stream/{sid}", cookie))
        await asyncio.sleep(0.01)
        llm.resume.set()
        for reply in await asyncio.gather(first, second):
            names = [name for name, _ in sse_events(reply.text)]
            assert names[0] == "status" and names[-1] == "done"
            assert tokens_text(sse_events(reply.text)) == "".join(DEFAULT_SCRIPT)

    run(app, scenario)


def test_stop_closes_the_llm_stream_frees_the_gate_and_drops_the_empty_conversation(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        other = await sign_up(app, "baraka")
        body = await ask(app, cookie)
        sid, cid = body["session_id"], body["conversation_id"]
        await wait_until(lambda: len(llm.prompts) == 1)
        assert (await call(app, "DELETE", f"/api/sessions/{sid}", cookie=other)).status == 404
        assert not llm.cancelled
        stopped = await call(app, "DELETE", f"/api/sessions/{sid}", cookie=cookie)
        assert stopped.json() == {"stopped": True}
        assert llm.cancelled
        assert rt.gate.active == 0
        session = rt.sessions.get(sid)
        assert session is not None and session.status == "aborted"
        assert (await get(app, f"/api/conversations/{cid}", cookie)).status == 404
        again = await call(app, "DELETE", f"/api/sessions/{sid}", cookie=cookie)
        assert again.json() == {"stopped": False}
        assert (await get(app, f"/api/stream/{sid}", cookie)).json()["error"]["code"] == "aborted"
        # The next question gets the gate at once.
        llm.pause_after = None
        nxt = await ask(app, cookie)
        await finished(rt, nxt["session_id"])
        assert status(rt, nxt["session_id"]) == "done"

    run(app, scenario)


def test_guest_sessions_cannot_be_stopped_by_delete(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM())

    async def scenario(rt: Runtime) -> None:
        sid = (await ask(app, None))["session_id"]
        assert (await call(app, "DELETE", f"/api/sessions/{sid}")).status == 404

    run(app, scenario)


def test_events_reach_only_the_sign_in_that_asked(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        asker = await sign_up(app, "amina")
        same_user_elsewhere = await sign_in(app, "amina")
        stranger = await sign_up(app, "baraka")
        sid = (await ask(app, asker))["session_id"]
        mine = asyncio.create_task(call(app, "GET", "/api/events", cookie=asker, disconnect_when=lambda b: "turn" in b))
        others = [
            asyncio.create_task(call(app, "GET", "/api/events", cookie=c, disconnect_after=0.3))
            for c in (same_user_elsewhere, stranger)
        ]
        await wait_until(lambda: sum(rt.hub.listening(k) for k in rt.hub._listeners) == 3)
        llm.resume.set()
        assert [name for name, _ in sse_events((await mine).text)] == ["turn_done"]
        for reply in await asyncio.gather(*others):
            assert sse_events(reply.text) == []
        assert (await get(app, "/api/events", None)).status == 401
        assert sid

    run(app, scenario)


def test_events_wait_in_a_backlog_until_the_sign_in_connects(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM(fail_with=RuntimeError("boom")))

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        body = await ask(app, cookie)
        await finished(rt, body["session_id"])
        reply = await call(app, "GET", "/api/events", cookie=cookie, disconnect_when=lambda b: "turn_failed" in b)
        (event,) = sse_events(reply.text)
        # The first answer failed, so its empty conversation is gone too.
        assert event == ("turn_failed", {"session_id": body["session_id"], "conversation_id": None, "code": "internal"})
        assert (await get(app, f"/api/conversations/{body['conversation_id']}", cookie)).status == 404

    run(app, scenario)


def test_turn_is_saved_only_when_unlocked_with_history_on(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM())

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        prefs = {"save_history": False, "auto_lock_minutes": 15}
        assert (await call(app, "PUT", "/api/account/prefs", body=prefs, cookie=cookie)).status == 200
        private = await ask(app, cookie)
        assert private["conversation_id"] is None and private["background"] is True
        await finished(rt, private["session_id"])
        assert status(rt, private["session_id"]) == "done"
        assert (await get(app, "/api/conversations", cookie)).json() == {"items": [], "next_cursor": None}
        await call(app, "POST", "/api/auth/lock", cookie=cookie)
        locked = await call(app, "POST", "/api/query", body={"question": EN_QUESTION}, cookie=cookie)
        assert locked.status == 423
        assert (await get(app, "/api/conversations", cookie)).status == 423

    run(app, scenario)


def test_in_response_run_of_a_signed_in_user_is_saved_too(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM())

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        body = await ask(app, cookie, background=False)
        assert body["background"] is False
        reply = await get(app, f"/api/stream/{body['session_id']}", cookie)
        assert sse_events(reply.text)[-1][0] == "done"  # the response's background task has saved the turn
        detail = (await get(app, f"/api/conversations/{body['conversation_id']}", cookie)).json()
        assert len(detail["thread"]) == 1

    run(app, scenario)


def test_null_response_turn_is_saved_at_once(tmp_path: Path) -> None:
    llm = FakeLLM()
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        body = await ask(app, cookie, question=GARBAGE)
        assert body["null_response"] is True and body["background"] is False
        (turn,) = (await get(app, f"/api/conversations/{body['conversation_id']}", cookie)).json()["thread"]
        assert turn["null_response"] is True
        assert turn["sources"] == [] and turn["sections"] == {"rights": "", "steps": "", "letter": ""}
        assert llm.prompts == []

    run(app, scenario)


def test_follow_up_adds_the_earlier_question_to_retrieval_and_the_prompt(tmp_path: Path) -> None:
    llm = FakeLLM()
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        first = await ask(app, cookie)
        await finished(rt, first["session_id"])
        assert rt.pipeline is not None
        seen: list[str] = []
        original = rt.pipeline.retrieve_context

        def spy(question: str) -> Any:
            seen.append(question)
            return original(question)

        vars(rt.pipeline)["retrieve_context"] = spy  # instance attribute shadows the method
        second = await ask(app, cookie, question=FOLLOW_UP, conversation_id=first["conversation_id"])
        assert second["conversation_id"] == first["conversation_id"]
        await finished(rt, second["session_id"])
        assert seen == [f"{EN_QUESTION} {FOLLOW_UP}"]
        assert llm.prompts[-1].endswith(
            f"USER QUESTION: Earlier question: <question>{EN_QUESTION}</question>\n"
            f"Question: <question>{FOLLOW_UP}</question>"
        )
        thread = (await get(app, f"/api/conversations/{first['conversation_id']}", cookie)).json()["thread"]
        assert [t["question"] for t in thread] == [EN_QUESTION, FOLLOW_UP]
        assert [t["idx"] for t in thread] == [0, 1]

    run(app, scenario)


def test_follow_up_needs_the_askers_own_saved_conversation(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM())

    async def scenario(rt: Runtime) -> None:
        owner = await sign_up(app, "amina")
        stranger = await sign_up(app, "baraka")
        cid = (await ask(app, owner))["conversation_id"]
        for cookie in (stranger, None):
            reply = await call(
                app, "POST", "/api/query", body={"question": FOLLOW_UP, "conversation_id": cid}, cookie=cookie
            )
            assert reply.status == 404
            assert reply.json()["error"]["code"] == "conversation_not_found"

    run(app, scenario)


def test_a_signed_in_users_session_is_hidden_from_others(tmp_path: Path) -> None:
    app = make_app(tmp_path, FakeLLM())

    async def scenario(rt: Runtime) -> None:
        owner = await sign_up(app, "amina")
        stranger = await sign_up(app, "baraka")
        sid = (await ask(app, owner))["session_id"]
        await finished(rt, sid)
        for path in (f"/api/stream/{sid}", f"/api/sources/{sid}", f"/api/letter/{sid}"):
            assert (await get(app, path, stranger)).status == 404
            assert (await get(app, path, None)).status == 404
        assert (await get(app, f"/api/sources/{sid}", owner)).status == 200

    run(app, scenario)


def test_conversation_deleted_while_answering_is_not_recreated(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)
    app = make_app(tmp_path, llm)

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        body = await ask(app, cookie)
        await wait_until(lambda: len(llm.prompts) == 1)
        assert (await call(app, "DELETE", f"/api/conversations/{body['conversation_id']}", cookie=cookie)).status == 200
        llm.resume.set()
        await finished(rt, body["session_id"])
        assert (await get(app, "/api/conversations", cookie)).json()["items"] == []

    run(app, scenario)


def test_shutdown_cancels_running_background_answers(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)
    app = make_app(tmp_path, llm)
    seen: dict[str, Any] = {}

    async def scenario(rt: Runtime) -> None:
        cookie = await sign_up(app, "amina")
        await ask(app, cookie)
        await wait_until(lambda: len(llm.prompts) == 1)
        seen["rt"] = rt

    run(app, scenario)
    assert llm.cancelled
    assert seen["rt"].runs == {}
