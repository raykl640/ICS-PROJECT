"""FastAPI app (ARCHITECTURE §8, §10): query -> SSE stream -> sources / letter / feedback, health, static frontend.

Run:  uvicorn backend.app.main:app                          real stack (indexes, cached models, Ollama)
      HAKI_FAKE_BACKENDS=1 uvicorn backend.app.main:app     synthetic corpus + fake models, for frontend work
Every non-2xx body is {"error": {"code", "message"}} (health adds the same "error" key to its 503 body).
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
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

from backend.app.config import get_settings
from backend.app.deps import Deps, default_deps
from backend.app.feedback import append_feedback
from backend.app.generation.gate import GateFull, LLMGate, Ticket
from backend.app.generation.prompt import build_prompt
from backend.app.lang.service import LanguageService, load_ui_strings
from backend.app.letter import letter_docx, letter_text
from backend.app.logging_setup import configure_logging
from backend.app.models import (
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
from backend.app.security import RateLimiter, clean_comment, clean_question
from backend.app.sessions import SessionsFull, SessionStore
from backend.app.stream import AnswerStream
from backend.app.web import BodyLimitMiddleware, SecurityHeadersMiddleware, SPAStaticFiles, error_response

log = logging.getLogger("hakiai.api")

SETUP_OFFLINE_COMMAND = "python scripts/setup_offline.py"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_WARMUP_EN = "My employer dismissed me without notice."
_WARMUP_SW = "Mwajiri wangu alinifukuza kazi bila notisi."
_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}
_NOT_STREAMABLE: dict[str, tuple[str, str]] = {
    "running": ("in_progress", "This answer is being generated on another connection."),
    "aborted": ("aborted", "This answer was interrupted. Please ask the question again."),
    "error": ("generation_failed", "This answer failed. Please ask the question again."),
}


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
    pipeline: ContextPipeline | None = None
    models_warm: bool = False


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


def _session(rt: Runtime, session_id: str) -> SessionData:
    """The live session or 404."""
    session = rt.sessions.get(session_id)
    if session is None:
        raise ApiError(404, "session_not_found", "Unknown or expired session. Please ask the question again.")
    return session


def _busy(rt: Runtime, message: str) -> ApiError:
    """503 asking the client to come back later."""
    return ApiError(503, "busy", message, {"Retry-After": str(rt.deps.settings.busy_retry_after_s)})


def _flag_truncated(question_en: str, chunks: list[RetrievedChunk], rt: Runtime) -> list[RetrievedChunk]:
    """Mark the chunks the prompt budget will shorten or drop, so /api/sources can say so."""
    if not chunks:
        return []
    truncated = set(build_prompt(question_en, [c.chunk for c in chunks], rt.deps.settings).truncated_ids)
    return [c.model_copy(update={"truncated": c.chunk.chunk_id in truncated}) for c in chunks]


@api.post("/query")
async def query(body: QueryRequest, request: Request, rt: RT) -> QueryResponse:
    """Retrieve and rerank context for a question and open a session; the answer streams from /api/stream/{id}."""
    settings = rt.deps.settings
    question = clean_question(body.question, settings.max_question_chars)
    if not question:
        raise ApiError(422, "empty_question", "The question is empty after removing control characters.")
    _check_rate(rt.query_limiter, request)
    if rt.pipeline is None:
        raise ApiError(503, "not_ready", "The service is still starting. Please try again shortly.")
    prepared = await run_in_threadpool(rt.deps.language.prepare_query, question, body.language)
    result = await run_in_threadpool(rt.pipeline.retrieve_context, prepared.english)
    session = SessionData(
        question=question,
        question_en=prepared.english,
        lang=prepared.original_lang,
        chunks=_flag_truncated(prepared.english, result.chunks, rt),
        fallback=result.null,
        acts=result.debug.acts or [],
        status="done" if result.null else "pending",
    )
    try:
        session_id = rt.sessions.create(session)
    except SessionsFull as exc:
        raise _busy(rt, "Too many answers are being generated. Please try again shortly.") from exc
    log.info(
        "query",
        extra={
            "session_id": session_id,
            "lang": session.lang,
            "translated": prepared.translated,
            "null_response": result.null,
            "chunks": len(session.chunks),
            "acts": session.acts,
            "retrieval_ms": round(result.debug.timings_ms["total"]),
        },
    )
    return QueryResponse(session_id=session_id, null_response=result.null, acts=session.acts, language=session.lang)


async def _finish_run(
    session_id: str, session: SessionData, events: AsyncGenerator[ServerSentEvent, None], ticket: Ticket
) -> None:
    """After the response ends (finished or client gone): close the run, free the gate, mark unfinished runs aborted."""
    await events.aclose()
    ticket.release()
    if session.status == "running":
        session.status = "aborted"
        log.info("generation_aborted", extra={"session_id": session_id})


@api.get("/stream/{session_id}", response_class=EventSourceResponse)
async def stream(session_id: str, rt: RT) -> EventSourceResponse:
    """SSE answer stream (events in backend/app/stream.py); generated once, replayed on later connections."""
    session = _session(rt, session_id)
    ping = rt.deps.settings.sse_ping_s
    if session.status == "done":
        return EventSourceResponse(rt.answers.replay(session), ping=ping)
    if session.status in _NOT_STREAMABLE:
        raise ApiError(409, *_NOT_STREAMABLE[session.status])
    try:
        ticket = rt.gate.enter()
    except GateFull as exc:
        raise _busy(rt, "Too many people are waiting for an answer. Please try again shortly.") from exc
    session.status = "running"
    events = rt.answers.run(session_id, session, ticket)
    finish = BackgroundTask(_finish_run, session_id, session, events, ticket)
    return EventSourceResponse(events, ping=ping, background=finish)


@api.get("/sources/{session_id}", response_model_exclude_none=True)
async def sources(session_id: str, rt: RT) -> SourcesResponse:
    """The retrieved chunks, verbatim, in rank order (empty for a null response)."""
    session = _session(rt, session_id)
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
    session_id: str, rt: RT, fmt: Annotated[Literal["txt", "docx"], Query(alias="format")] = "txt"
) -> Response:
    """The FORMAL LETTER section (Kiswahili when the user asked in Kiswahili) as .txt or .docx, with the disclaimer."""
    session = _session(rt, session_id)
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
    session = _session(rt, body.session_id)
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


def _warm_up(pipeline: ContextPipeline, language: LanguageService) -> None:
    """One tiny call through every lazy model (embedder, cross-encoder, both translators)."""
    try:
        pipeline.retrieve_context(_WARMUP_EN)
        language.prepare_query(_WARMUP_SW, "sw")
        language.translate_result(ParsedResponse(rights=_WARMUP_EN))
    except OSError as exc:
        raise StartupError(
            f"a model could not be loaded from the local cache ({type(exc).__name__}: {exc}). "
            f"Download the models once with: {SETUP_OFFLINE_COMMAND}"
        ) from exc


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
        if dropped:
            log.info("sessions_purged", extra={"count": dropped, "live": len(rt.sessions)})


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: logging, indexes (fail fast), model warm-up, Ollama check, purge task. Shutdown: stop the task."""
    rt: Runtime = app.state.runtime
    deps = rt.deps
    if deps.setup_logging:
        configure_logging(deps.settings)
    rt.pipeline = await run_in_threadpool(_load_pipeline, deps)
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


def _install_error_handlers(app: FastAPI) -> None:
    """Map every error to {"error": {"code", "message"}}; validation messages never echo the input."""

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.headers)

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


def create_app(deps: Deps, clock: Callable[[], float] = time.monotonic) -> FastAPI:
    """The API with its middleware and, if built, the frontend (mounted after the API routes)."""
    s = deps.settings
    app = FastAPI(title="HakiAI API", version="0.1.0", lifespan=_lifespan)
    app.state.runtime = Runtime(
        deps=deps,
        sessions=SessionStore(s.session_ttl_s, s.max_sessions, clock),
        gate=LLMGate(s.max_queue),
        query_limiter=RateLimiter(s.rate_limit_per_min, clock),
        feedback_limiter=RateLimiter(s.rate_limit_per_min, clock),
        answers=AnswerStream(s, deps.llm, deps.language, deps.refs, load_ui_strings(s.ui_strings_path)),
    )
    _install_error_handlers(app)
    app.include_router(api)
    if s.dev_mode:
        app.add_middleware(
            CORSMiddleware, allow_origins=[s.cors_dev_origin], allow_methods=["GET", "POST"], allow_headers=["*"]
        )
    app.add_middleware(BodyLimitMiddleware, max_bytes=s.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    if (s.frontend_dist / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=s.frontend_dist, html=True), name="frontend")
    return app


app = create_app(default_deps(get_settings()))
