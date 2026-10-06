"""FastAPI app (ARCHITECTURE §8, §10): query -> SSE stream -> sources / letter / feedback, health, static frontend.

Run:  uvicorn backend.app.main:app                          real stack (indexes, cached models, Ollama)
      HAKI_FAKE_BACKENDS=1 uvicorn backend.app.main:app     synthetic corpus + fake models, for frontend work
Every non-2xx body is {"error": {"code", "message"}} (health adds the same "error" key to its 503 body).
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import aclosing, asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.accounts.auth import AuthSession, AuthSessions
from backend.app.accounts.db import Database
from backend.app.accounts.library import Library, NewTurn, Sections, not_found
from backend.app.accounts.library_routes import library as library_routes
from backend.app.accounts.routes import COOKIE
from backend.app.accounts.routes import account as account_routes
from backend.app.accounts.routes import auth as auth_routes
from backend.app.accounts.service import AccountError, Accounts
from backend.app.config import get_settings
from backend.app.deps import Deps, default_deps, warm_up
from backend.app.feedback import append_feedback
from backend.app.generation.gate import GateFull, LLMGate, Ticket
from backend.app.generation.prompt import build_prompt
from backend.app.lang.service import LanguageService, load_ui_strings
from backend.app.laws.catalog import LawCatalog
from backend.app.laws.routes import laws as laws_routes
from backend.app.letter import letter_docx, letter_text
from backend.app.logging_setup import configure_logging
from backend.app.models import (
    CitationCheck,
    FeedbackIn,
    FeedbackOut,
    ParsedResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
    SessionData,
    SourceChunk,
    SourcesResponse,
)
from backend.app.retrieval.meta import REBUILD_COMMAND
from backend.app.retrieval.pipeline import ContextPipeline
from backend.app.runs import EventHub, RunBuffer
from backend.app.security import RateLimiter, clean_comment, clean_question
from backend.app.sessions import SessionsFull, SessionStore
from backend.app.stream import AnswerStream, sse
from backend.app.web import (
    BodyLimitMiddleware,
    RequestGuardMiddleware,
    SecurityHeadersMiddleware,
    SPAStaticFiles,
    error_response,
)

log = logging.getLogger("hakiai.api")

SETUP_OFFLINE_COMMAND = "python scripts/setup_offline.py"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}
_NOT_STREAMABLE: dict[str, tuple[str, str]] = {
    "running": ("in_progress", "This answer is being generated on another connection."),
    "aborted": ("aborted", "This answer was interrupted. Please ask the question again."),
    "error": ("generation_failed", "This answer failed. Please ask the question again."),
}
STOPPED_MESSAGE = "You stopped this answer."


class ApiError(Exception):
    """An error response with a stable machine-readable code."""

    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


class StartupError(RuntimeError):
    """The app cannot start; the message says how to fix it."""


@dataclass
class Runtime:
    """Per-app state: dependencies, the loaded pipeline, sessions, the LLM gate and rate limiters."""

    deps: Deps
    sessions: SessionStore
    gate: LLMGate
    query_limiter: RateLimiter
    feedback_limiter: RateLimiter
    answers: AnswerStream
    hub: EventHub
    wall_clock: Callable[[], float] = time.time
    pipeline: ContextPipeline | None = None
    models_warm: bool = False
    accounts: Accounts | None = None
    library: Library | None = None
    runs: dict[str, RunBuffer] = field(default_factory=dict)


async def _runtime(request: Request) -> Runtime:
    """The Runtime of the app serving request (async, so FastAPI does not hop to a worker thread for it)."""
    rt: Runtime = request.app.state.runtime
    return rt


RT = Annotated[Runtime, Depends(_runtime)]
api = APIRouter(prefix="/api")


def _check_rate(limiter: RateLimiter, request: Request) -> None:
    """429 with Retry-After when the client IP has used up its budget."""
    key = request.client.host if request.client else "unknown"
    if not limiter.allow(key):
        retry = str(limiter.retry_after(key))
        raise ApiError(429, "rate_limited", "Too many requests. Please wait and try again.", {"Retry-After": retry})


def _caller(request: Request, rt: Runtime) -> AuthSession | None:
    """The sign-in behind the request's cookie, if any (locked or not)."""
    if rt.accounts is None:
        return None
    return rt.accounts.session(request.cookies.get(COOKIE))


def _session(rt: Runtime, session_id: str, request: Request) -> SessionData:
    """The live session or 404; a signed-in user's session is visible to that user only."""
    session = rt.sessions.get(session_id)
    if session is not None and session.owner_id is not None:
        caller = _caller(request, rt)
        if caller is None or caller.user_id != session.owner_id:
            session = None
    if session is None:
        raise ApiError(404, "session_not_found", "Unknown or expired session. Please ask the question again.")
    return session


@dataclass(frozen=True)
class _Asker:
    """A signed-in, unlocked asker; save_key is their data key when "Save history" is on (else None)."""

    user_id: str
    auth_key: str
    save_key: bytes | None


def _asker(request: Request, rt: Runtime) -> _Asker | None:
    """Who is asking: None for guests, 423 when the sign-in is locked (asking counts as activity)."""
    session = _caller(request, rt)
    if session is None or rt.accounts is None:
        return None
    if session.dek is None:
        raise AccountError(423, "locked", "HakiAI is locked. Enter your password to continue.")
    rt.accounts.sessions.touch(session)
    keep = rt.accounts.prefs(session).save_history
    return _Asker(session.user_id, session.token_hash, session.dek if keep else None)


async def _earlier(rt: Runtime, asker: _Asker | None, conversation_id: str | None) -> list[str]:
    """English questions a follow-up builds on (D23); only in the asker's own saved conversations."""
    if conversation_id is None:
        return []
    if asker is None or asker.save_key is None or rt.library is None:
        raise not_found("conversation")
    return await run_in_threadpool(rt.library.earlier_questions, asker.user_id, asker.save_key, conversation_id)


def _busy(rt: Runtime, message: str) -> ApiError:
    """503 asking the client to come back later."""
    return ApiError(503, "busy", message, {"Retry-After": str(rt.deps.settings.busy_retry_after_s)})


def _flag_truncated(
    question_en: str, chunks: list[RetrievedChunk], rt: Runtime, earlier: list[str]
) -> list[RetrievedChunk]:
    """Mark the chunks the prompt budget will shorten or drop, so /api/sources can say so."""
    if not chunks:
        return []
    prompt = build_prompt(question_en, [c.chunk for c in chunks], rt.deps.settings, earlier)
    truncated = set(prompt.truncated_ids)
    return [c.model_copy(update={"truncated": c.chunk.chunk_id in truncated}) for c in chunks]


@api.post("/query")
async def query(body: QueryRequest, request: Request, rt: RT) -> QueryResponse:
    """Retrieve and rerank context for a question and open a session; the answer streams from /api/stream/{id}.

    Signed in: the turn is saved (history on), a follow-up adds the earlier question to retrieval (D23), and by
    default the answer is generated in the background, surviving a disconnect (D24)."""
    settings = rt.deps.settings
    question = clean_question(body.question, settings.max_question_chars)
    if not question:
        raise ApiError(422, "empty_question", "The question is empty after removing control characters.")
    _check_rate(rt.query_limiter, request)
    if rt.pipeline is None:
        raise ApiError(503, "not_ready", "The service is still starting. Please try again shortly.")
    asker = await run_in_threadpool(_asker, request, rt)
    earlier = await _earlier(rt, asker, body.conversation_id)
    prepared = await run_in_threadpool(rt.deps.language.prepare_query, question, body.language)
    result = await run_in_threadpool(rt.pipeline.retrieve_context, " ".join([*earlier, prepared.english]))
    background = asker is not None and settings.background_runs and body.background is not False and not result.null
    session = SessionData(
        question=question,
        question_en=prepared.english,
        lang=prepared.original_lang,
        chunks=_flag_truncated(prepared.english, result.chunks, rt, earlier),
        fallback=result.null,
        acts=result.debug.acts or [],
        status="done" if result.null else "pending",
        earlier_en=earlier,
        background=background,
    )
    ticket = _enter_gate(rt) if background else None
    try:
        await _attach_owner(rt, session, asker, body.conversation_id)
        session_id = _create_session(rt, session)
    except BaseException:
        if ticket is not None:
            ticket.release()
        await _drop_new_conversation(rt, session)
        raise
    if result.null:
        await _after_run(rt, session_id, session)
    elif ticket is not None:
        _start_background(rt, session_id, session, ticket)
    log.info(
        "query",
        extra={
            "session_id": session_id,
            "lang": session.lang,
            "translated": prepared.translated,
            "null_response": result.null,
            "chunks": len(session.chunks),
            "acts": session.acts,
            "follow_up": bool(earlier),
            "background": background,
            "retrieval_ms": round(result.debug.timings_ms["total"]),
        },
    )
    return QueryResponse(
        session_id=session_id,
        null_response=result.null,
        acts=session.acts,
        language=session.lang,
        conversation_id=session.conversation_id,
        background=background,
    )


def _enter_gate(rt: Runtime) -> Ticket:
    """A place in the LLM queue, or 503 busy."""
    try:
        return rt.gate.enter()
    except GateFull as exc:
        raise _busy(rt, "Too many people are waiting for an answer. Please try again shortly.") from exc


def _create_session(rt: Runtime, session: SessionData) -> str:
    """Store the session, or 503 busy when every slot is generating."""
    try:
        return rt.sessions.create(session)
    except SessionsFull as exc:
        raise _busy(rt, "Too many answers are being generated. Please try again shortly.") from exc


async def _attach_owner(rt: Runtime, session: SessionData, asker: _Asker | None, conversation_id: str | None) -> None:
    """Record the signed-in asker on the session and, with history on, the conversation the turn goes into."""
    if asker is None:
        return
    session.owner_id = asker.user_id
    session.auth_key = asker.auth_key
    if asker.save_key is None or rt.library is None:
        return
    session.save_key = asker.save_key
    if conversation_id is None:
        conversation_id = await run_in_threadpool(
            rt.library.create_conversation, asker.user_id, asker.save_key, session.question, session.lang
        )
        session.new_conversation = True
    session.conversation_id = conversation_id


def _new_turn(rt: Runtime, session_id: str, session: SessionData) -> NewTurn:
    """The finished session as a turn to save (sections in the user's language)."""
    parsed = session.parsed_user or session.parsed or ParsedResponse()
    return NewTurn(
        question=session.question,
        question_en=session.question_en,
        lang=session.lang,
        sections=Sections(rights=parsed.rights, steps=parsed.steps, letter=parsed.letter),
        answer_en=session.answer_en,
        sources=[(c.chunk.chunk_id, c.rerank_score) for c in session.chunks],
        acts=session.acts,
        citation_check=session.citation_check or CitationCheck(),
        format_ok=session.parsed.format_ok if session.parsed else True,
        warnings=[] if session.fallback else rt.answers.warnings(session),
        truncated_chunks=[c.chunk.chunk_id for c in session.chunks if c.truncated],
        untranslated=session.untranslated,
        null_response=session.fallback,
        session_id=session_id,
    )


async def _drop_new_conversation(rt: Runtime, session: SessionData) -> None:
    """Delete the conversation created for this question if no turn reached it."""
    session.save_key = None
    if rt.library is None or session.owner_id is None or session.conversation_id is None:
        return
    if session.new_conversation:
        await run_in_threadpool(rt.library.drop_if_empty, session.owner_id, session.conversation_id)
        session.conversation_id = None


async def _after_run(rt: Runtime, session_id: str, session: SessionData) -> str | None:
    """Save a finished turn (signed in, history on) and drop the data key; a new conversation whose first answer did
    not finish is deleted again. Returns the saved turn id."""
    owner, key, conversation_id = session.owner_id, session.save_key, session.conversation_id
    session.save_key = None
    if rt.library is None or owner is None or key is None or conversation_id is None:
        return None
    if session.status != "done":
        await _drop_new_conversation(rt, session)
        return None
    try:
        turn_id = await run_in_threadpool(
            rt.library.add_turn, owner, key, conversation_id, _new_turn(rt, session_id, session)
        )
    except AccountError:
        log.info("turn_not_saved", extra={"session_id": session_id, "reason": "conversation_deleted"})
        return None
    log.info("turn_saved", extra={"session_id": session_id, "turn_id": turn_id})
    return turn_id


def _start_background(rt: Runtime, session_id: str, session: SessionData, ticket: Ticket) -> None:
    """Generate the answer in a server task that outlives the client's connection (D24)."""
    buffer = RunBuffer()
    session.status = "running"
    rt.runs[session_id] = buffer
    buffer.task = asyncio.create_task(_drive(rt, session_id, session, ticket, buffer))
    buffer.task.add_done_callback(lambda _: _retire(rt, session_id, session, ticket, buffer))


def _settle(session: SessionData, ticket: Ticket, buffer: RunBuffer) -> None:
    """End of generation: free the gate, end the followers, mark an unfinished run aborted (idempotent)."""
    ticket.release()
    buffer.finish()
    if session.status in ("pending", "running"):
        session.status = "aborted"


def _retire(rt: Runtime, session_id: str, session: SessionData, ticket: Ticket, buffer: RunBuffer) -> None:
    """When the run's task is over (saved and notified, or cancelled before it started): settle and forget it."""
    _settle(session, ticket, buffer)
    rt.runs.pop(session_id, None)


async def _drive(rt: Runtime, session_id: str, session: SessionData, ticket: Ticket, buffer: RunBuffer) -> None:
    """Run the answer into the buffer; cancellation (DELETE /api/sessions/{id}) closes the LLM stream. Then save the
    turn and notify the sign-in that asked."""
    try:
        async with aclosing(rt.answers.run(session_id, session, ticket)) as events:
            async for event in events:
                buffer.push(event)
    except asyncio.CancelledError:
        session.status = "aborted"
        buffer.push(sse("error", {"code": "stopped", "message": STOPPED_MESSAGE}))
        log.info("generation_stopped", extra={"session_id": session_id})
    finally:
        _settle(session, ticket, buffer)
    turn_id = await _after_run(rt, session_id, session)
    _notify(rt, session_id, session, turn_id)


def _notify(rt: Runtime, session_id: str, session: SessionData, turn_id: str | None) -> None:
    """turn_done / turn_failed to the sign-in that asked (nothing for a run the user stopped)."""
    if session.auth_key is None:
        return
    payload = {"session_id": session_id, "conversation_id": session.conversation_id}
    if session.status == "done":
        rt.hub.publish(session.auth_key, "turn_done", payload | {"turn_id": turn_id})
    elif session.status == "error":
        rt.hub.publish(session.auth_key, "turn_failed", payload | {"code": session.error_code or "internal"})


async def _finish_run(
    rt: Runtime, session_id: str, session: SessionData, events: AsyncGenerator[ServerSentEvent, None], ticket: Ticket
) -> None:
    """After the response ends (finished or client gone): close the run, free the gate, mark unfinished runs aborted,
    then save a signed-in user's finished turn."""
    await events.aclose()
    ticket.release()
    if session.status == "running":
        session.status = "aborted"
        log.info("generation_aborted", extra={"session_id": session_id})
    await _after_run(rt, session_id, session)


@api.get("/stream/{session_id}", response_class=EventSourceResponse)
async def stream(session_id: str, request: Request, rt: RT) -> EventSourceResponse:
    """SSE answer stream (events in backend/app/stream.py); generated once, replayed on later connections.

    A background run is followed from its first event by any number of connections; leaving does not stop it."""
    session = _session(rt, session_id, request)
    ping = rt.deps.settings.sse_ping_s
    if session.status == "done":
        return EventSourceResponse(rt.answers.replay(session), ping=ping)
    buffer = rt.runs.get(session_id)
    if buffer is not None:
        return EventSourceResponse(buffer.follow(), ping=ping)
    if session.status in _NOT_STREAMABLE:
        raise ApiError(409, *_NOT_STREAMABLE[session.status])
    ticket = _enter_gate(rt)
    session.status = "running"
    events = rt.answers.run(session_id, session, ticket)
    finish = BackgroundTask(_finish_run, rt, session_id, session, events, ticket)
    return EventSourceResponse(events, ping=ping, background=finish)


@api.delete("/sessions/{session_id}")
async def stop(session_id: str, request: Request, rt: RT) -> dict[str, bool]:
    """Stop the caller's background run: the LLM stream is closed and the gate freed before this returns.

    stopped=false when it had already finished; guests stop by closing the stream (404 here)."""
    session = _session(rt, session_id, request)
    if session.owner_id is None:
        raise ApiError(404, "session_not_found", "Unknown or expired session. Please ask the question again.")
    buffer = rt.runs.get(session_id)
    task = buffer.task if buffer else None
    if task is None or task.done():
        return {"stopped": False}
    task.cancel()
    await asyncio.wait({task})
    return {"stopped": True}


@api.get("/events", response_class=EventSourceResponse)
async def events(request: Request, rt: RT) -> EventSourceResponse:
    """turn_done / turn_failed {session_id, conversation_id, turn_id | code} for this sign-in's background runs."""
    caller = await run_in_threadpool(_caller, request, rt)
    if caller is None:
        raise AccountError(401, "auth_required", "Please sign in.")
    return EventSourceResponse(rt.hub.subscribe(caller.token_hash), ping=rt.deps.settings.sse_ping_s)


@api.get("/sources/{session_id}", response_model_exclude_none=True)
async def sources(session_id: str, request: Request, rt: RT) -> SourcesResponse:
    """The retrieved chunks, verbatim, in rank order (empty for a null response)."""
    session = _session(rt, session_id, request)
    debug = rt.deps.settings.debug_scores
    chunks = [
        SourceChunk(
            chunk_id=c.chunk.chunk_id,
            act=c.chunk.act,
            unit_type=c.chunk.unit_type,
            section_num=c.chunk.section_num,
            section_title=c.chunk.section_title,
            part=c.chunk.part,
            page=c.chunk.page,
            text=c.chunk.text,
            truncated=c.truncated,
            rank=rank,
            rerank_score=c.rerank_score if debug else None,
        )
        for rank, c in enumerate(session.chunks, 1)
    ]
    return SourcesResponse(session_id=session_id, chunks=chunks)


def _attachment(filename: str) -> dict[str, str]:
    """Download header for an exported file."""
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@api.get("/letter/{session_id}")
async def letter(
    session_id: str,
    request: Request,
    rt: RT,
    fmt: Annotated[Literal["txt", "docx"], Query(alias="format")] = "txt",
) -> Response:
    """The FORMAL LETTER section (Kiswahili when the user asked in Kiswahili) as .txt or .docx, with the disclaimer."""
    session = _session(rt, session_id, request)
    if session.fallback:
        raise ApiError(404, "no_letter", "There is no letter because no answer was generated for this question.")
    if session.status != "done":
        raise ApiError(409, "not_finished", "The answer is not finished yet.")
    parsed = session.parsed_user or session.parsed
    if parsed is None or not parsed.letter:
        raise ApiError(404, "no_letter", "The answer has no formal letter section.")
    disclaimer = rt.answers.ui[session.lang]["disclaimer"]
    if fmt == "docx":
        return Response(letter_docx(parsed, disclaimer), media_type=DOCX_MEDIA_TYPE, headers=_attachment("letter.docx"))
    return PlainTextResponse(letter_text(parsed, disclaimer), headers=_attachment("letter.txt"))


@api.post("/feedback")
async def feedback(body: FeedbackIn, request: Request, rt: RT) -> FeedbackOut:
    """Record a thumbs up/down once per session: ids, rating, comment and flags only, never question or answer."""
    _check_rate(rt.feedback_limiter, request)
    session = _session(rt, body.session_id, request)
    if session.feedback_given:
        return FeedbackOut(recorded=False)
    settings = rt.deps.settings
    record = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "session_id": body.session_id,
        "rating": body.rating,
        "comment": clean_comment(body.comment, settings.max_comment_chars),
        "language": session.lang,
        "null_response": session.fallback,
        "chunk_ids": [c.chunk.chunk_id for c in session.chunks],
    }
    session.feedback_given = True  # before the await, so a concurrent duplicate is not appended twice
    try:
        await run_in_threadpool(append_feedback, settings.feedback_path, record)
    except OSError:
        session.feedback_given = False
        raise
    log.info("feedback", extra={"session_id": body.session_id, "rating": body.rating})
    return FeedbackOut(recorded=True)


def _health_problems(checks: dict[str, bool], rt: Runtime) -> str:
    """What is wrong and how to fix it, for the failed checks."""
    s = rt.deps.settings
    fixes = {
        "ollama": f"ollama is not reachable at {s.ollama_url} (start it: ollama serve)",
        "model_present": f"the model is not in ollama (run: ollama pull {s.ollama_model})",
        "indexes_loaded": f"indexes are not loaded (startup incomplete; build them with: {REBUILD_COMMAND})",
        "models_warm": "models are still loading",
    }
    return "; ".join(fixes[name] for name, ok in checks.items() if not ok)


@api.get("/health")
async def health(rt: RT) -> JSONResponse:
    """200 when Ollama, the model, the indexes and the local models are all ready, else 503 naming the fixes."""
    reachable, model_present = await rt.deps.llm.status()
    checks = {
        "ollama": reachable,
        "model_present": model_present,
        "indexes_loaded": rt.pipeline is not None,
        "models_warm": rt.models_warm,
    }
    ok = all(checks.values())
    body: dict[str, object] = {"status": "ok" if ok else "degraded", **checks}
    if not ok:
        body["error"] = {"code": "degraded", "message": _health_problems(checks, rt)}
    return JSONResponse(body, status_code=200 if ok else 503)


def _load_pipeline(deps: Deps) -> ContextPipeline:
    """Load indexes and models; IndexMismatchError already names the rebuild command, file errors get both fixes."""
    try:
        return deps.load_pipeline()
    except OSError as exc:
        raise StartupError(
            f"could not load the corpus or a model ({type(exc).__name__}: {exc}). "
            f"Build the indexes with: {REBUILD_COMMAND}; download the models once with: {SETUP_OFFLINE_COMMAND}"
        ) from exc


def _load_laws(deps: Deps) -> LawCatalog:
    """Load the laws catalog; a missing refs.json is an IndexMismatchError naming the rebuild command."""
    try:
        return deps.load_laws()
    except OSError as exc:
        raise StartupError(
            f"could not load the corpus ({type(exc).__name__}: {exc}). Build it with: {REBUILD_COMMAND}"
        ) from exc


def _warm_up(pipeline: ContextPipeline, language: LanguageService) -> None:
    """Warm every lazy model; a model missing from the local cache becomes a StartupError naming the fix."""
    try:
        warm_up(pipeline, language)
    except OSError as exc:
        raise StartupError(
            f"a model could not be loaded from the local cache ({type(exc).__name__}: {exc}). "
            f"Download the models once with: {SETUP_OFFLINE_COMMAND}"
        ) from exc


def _open_accounts(rt: Runtime) -> Accounts:
    """Open (and migrate) the accounts database; sign-ins start empty, so remembered ones come back locked."""
    s = rt.deps.settings
    return Accounts(s, Database(s.app_db_path), AuthSessions(rt.wall_clock), rt.wall_clock)


async def _check_ollama(deps: Deps) -> None:
    """Warn (not fail) at startup when Ollama or the model is missing; /api/health reports it too."""
    reachable, model_present = await deps.llm.status()
    if not reachable:
        log.warning("ollama_unreachable", extra={"hint": f"start Ollama (ollama serve) at {deps.settings.ollama_url}"})
    elif not model_present:
        log.warning("ollama_model_missing", extra={"hint": f"ollama pull {deps.settings.ollama_model}"})


async def _purge_loop(rt: Runtime) -> None:
    """Periodically drop expired sessions and idle rate-limit buckets."""
    while True:
        await asyncio.sleep(rt.deps.settings.session_purge_interval_s)
        dropped = rt.sessions.purge()
        rt.query_limiter.prune()
        rt.feedback_limiter.prune()
        if rt.accounts is not None:
            await run_in_threadpool(rt.accounts.purge)
        if dropped:
            log.info("sessions_purged", extra={"count": dropped, "live": len(rt.sessions)})


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: logging, indexes (fail fast), model warm-up, Ollama check, purge task. Shutdown: stop the task."""
    rt: Runtime = app.state.runtime
    deps = rt.deps
    if deps.setup_logging:
        configure_logging(deps.settings, level=logging.getLevelNamesMapping()[deps.settings.log_level])
    rt.accounts = await run_in_threadpool(_open_accounts, rt)
    app.state.accounts = rt.accounts
    rt.pipeline = await run_in_threadpool(_load_pipeline, deps)
    rt.library = Library(deps.settings, rt.accounts.db, rt.pipeline.find_chunk, rt.wall_clock)
    app.state.library = rt.library
    app.state.laws = await run_in_threadpool(_load_laws, deps)
    await run_in_threadpool(_warm_up, rt.pipeline, deps.language)
    rt.models_warm = True
    await _check_ollama(deps)
    log.info("startup_complete", extra={"fake_backends": deps.settings.fake_backends})
    purge = asyncio.create_task(_purge_loop(rt))
    try:
        yield
    finally:
        purge.cancel()
        with suppress(asyncio.CancelledError):
            await purge
        runs = [buffer.task for buffer in rt.runs.values() if buffer.task is not None]
        for task in runs:
            task.cancel()
        await asyncio.gather(*runs, return_exceptions=True)


def _install_error_handlers(app: FastAPI) -> None:
    """Map every error to {"error": {"code", "message"}}; validation messages never echo the input."""

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.headers)

    @app.exception_handler(AccountError)
    async def _account_error(request: Request, exc: AccountError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return error_response(exc.status, exc.code, exc.message, headers)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(".".join(map(str, e["loc"])) + f": {e['msg']}" for e in exc.errors())
        return error_response(422, "invalid_request", problems)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return error_response(exc.status_code, code, str(exc.detail), exc.headers)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", extra={"exc_type": type(exc).__name__, "path": request.url.path})
        return error_response(500, "internal", "Internal server error.")


def create_app(
    deps: Deps, clock: Callable[[], float] = time.monotonic, wall_clock: Callable[[], float] = time.time
) -> FastAPI:
    """The API with its middleware and, if built, the frontend (mounted after the API routes).

    clock (monotonic) drives answer sessions and rate limits; wall_clock (epoch seconds) drives accounts: lockouts,
    auto-lock, token expiry and stored timestamps."""
    s = deps.settings
    app = FastAPI(title="HakiAI API", version="0.1.0", lifespan=_lifespan)
    ui = load_ui_strings(s.ui_strings_path)
    app.state.runtime = Runtime(
        deps=deps,
        sessions=SessionStore(s.session_ttl_s, s.max_sessions, clock),
        gate=LLMGate(s.max_queue),
        query_limiter=RateLimiter(s.rate_limit_per_min, clock),
        feedback_limiter=RateLimiter(s.rate_limit_per_min, clock),
        answers=AnswerStream(s, deps.llm, deps.language, deps.refs, ui),
        hub=EventHub(s.events_backlog),
        wall_clock=wall_clock,
    )
    app.state.sessions = app.state.runtime.sessions
    app.state.ui_strings = ui
    app.state.auth_limiter = RateLimiter(s.auth_rate_limit_per_min, clock)
    _install_error_handlers(app)
    app.include_router(api)
    app.include_router(auth_routes)
    app.include_router(account_routes)
    app.include_router(library_routes)
    app.include_router(laws_routes)
    if s.dev_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[s.cors_dev_origin],
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["*"],
            allow_credentials=True,
        )
    app.add_middleware(BodyLimitMiddleware, max_bytes=s.max_body_bytes)
    app.add_middleware(RequestGuardMiddleware, allowed_hosts=s.allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    if (s.frontend_dist / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=s.frontend_dist, html=True), name="frontend")
    return app


app = create_app(default_deps(get_settings()))
