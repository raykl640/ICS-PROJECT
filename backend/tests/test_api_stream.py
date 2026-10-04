"""SSE behaviour that needs real concurrency: client disconnect cancels the LLM, one generation at a time (FIFO)."""

import asyncio
from pathlib import Path

from fastapi import FastAPI

from backend.tests.api_support import EN_QUESTION, call, make_app, runtime, sse_events, tokens_text, wait_until
from backend.tests.fakes import DEFAULT_SCRIPT, FakeLLM


async def _ask(app: FastAPI) -> str:
    reply = await call(app, "POST", "/api/query", body={"question": EN_QUESTION, "language": "en"})
    assert reply.status == 200, reply.text
    session_id: str = reply.json()["session_id"]
    return session_id


def test_client_disconnect_cancels_llm_and_aborts_session(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)  # first token, then waits forever
    app = make_app(tmp_path, llm)

    async def scenario() -> None:
        async with app.router.lifespan_context(app):
            sid = await _ask(app)
            reply = await call(app, "GET", f"/api/stream/{sid}", disconnect_when=lambda body: "event: token" in body)
            assert reply.status == 200
            assert tokens_text(sse_events(reply.text)) == DEFAULT_SCRIPT[0]
            assert llm.cancelled
            rt = runtime(app)
            session = rt.sessions.get(sid)
            assert session is not None
            assert session.status == "aborted"
            assert session.answer_en == DEFAULT_SCRIPT[0]
            assert rt.gate.active == 0
            again = await call(app, "GET", f"/api/stream/{sid}")
            assert again.status == 409
            assert again.json()["error"]["code"] == "aborted"

    asyncio.run(scenario())


def test_one_generation_at_a_time_in_arrival_order(tmp_path: Path) -> None:
    llm = FakeLLM(pause_after=1)
    app = make_app(tmp_path, llm)

    async def scenario() -> None:
        async with app.router.lifespan_context(app):
            rt = runtime(app)
            first, second = await _ask(app), await _ask(app)
            task_a = asyncio.create_task(call(app, "GET", f"/api/stream/{first}"))
            await wait_until(lambda: len(llm.prompts) == 1)
            task_b = asyncio.create_task(call(app, "GET", f"/api/stream/{second}"))
            await wait_until(lambda: rt.gate.waiting == 1)
            in_progress = await call(app, "GET", f"/api/stream/{first}")
            assert in_progress.status == 409
            assert in_progress.json()["error"]["code"] == "in_progress"
            assert len(llm.prompts) == 1  # the second stream is queued, not generating
            llm.resume.set()
            reply_a, reply_b = await asyncio.gather(task_a, task_b)
            events_b = sse_events(reply_b.text)
            stages = [data for name, data in events_b if name == "status"]
            assert stages == [
                {"stage": "retrieved", "chunks": 5},
                {"stage": "queued", "position": 1},
                {"stage": "generating"},
            ]
            for reply in (reply_a, reply_b):
                assert tokens_text(sse_events(reply.text)) == "".join(DEFAULT_SCRIPT)
            assert len(llm.prompts) == 2
            assert rt.gate.active == 0

    asyncio.run(scenario())
