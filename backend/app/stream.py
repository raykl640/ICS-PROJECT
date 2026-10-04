"""SSE events for GET /api/stream/{id}: one live generation per session, replayed from the session afterwards.

Events (JSON data): status {stage: retrieved|queued|generating|translating, chunks?, position?} · token {text, deltas}
· translated {sections} (Kiswahili only, replaces the English draft) · done {warnings, citation_check, format_ok,
truncated_chunks, untranslated, disclaimer} · null {message, disclaimer} · error {code, message}.
"""

import json
import logging
import time
from collections.abc import AsyncGenerator, Mapping
from contextlib import aclosing
from dataclasses import asdict, dataclass

from sse_starlette import ServerSentEvent
from starlette.concurrency import run_in_threadpool

from backend.app.config import Settings
from backend.app.generation.gate import Ticket
from backend.app.generation.llm import GenerationTimeout, ModelNotLoaded, OllamaError, OllamaUnavailable
from backend.app.generation.prompt import PromptBudgetError, build_prompt
from backend.app.generation.service import GenerationResult, generate_stream
from backend.app.interfaces import LLMClient
from backend.app.lang.service import LanguageService
from backend.app.letter import without_disclaimer
from backend.app.models import CitationCheck, ParsedResponse, SessionData, UserLanguage
from backend.app.retrieval.refs import RefExtractor

log = logging.getLogger("hakiai.stream")

_SECTIONS = ("rights", "steps", "letter")
# Most specific first: ModelNotLoaded and the others subclass OllamaError.
_ERROR_CODES: tuple[tuple[type[Exception], str], ...] = (
    (ModelNotLoaded, "model_not_loaded"),
    (OllamaUnavailable, "llm_unavailable"),
    (GenerationTimeout, "llm_timeout"),
    (OllamaError, "llm_error"),
    (PromptBudgetError, "prompt_budget"),
)


def sse(name: str, data: Mapping[str, object]) -> ServerSentEvent:
    """One named SSE event with a JSON payload."""
    return ServerSentEvent(data=json.dumps(data, ensure_ascii=False), event=name)


def error_info(exc: Exception) -> tuple[str, str]:
    """(code, message) for a generation failure; unexpected errors get a generic message (no internals)."""
    for exc_type, code in _ERROR_CODES:
        if isinstance(exc, exc_type):
            return code, str(exc)
    return "internal", "Generation failed unexpectedly. Please try again."


def _sections(parsed: ParsedResponse) -> dict[str, str]:
    """The three sections as a plain dict."""
    return {key: getattr(parsed, key) for key in _SECTIONS}


@dataclass(frozen=True)
class AnswerStream:
    """Builds the event stream for a session: a live run (once) or a replay of the stored result."""

    settings: Settings
    llm: LLMClient
    language: LanguageService
    refs: RefExtractor
    ui: Mapping[UserLanguage, Mapping[str, str]]

    async def run(self, session_id: str, session: SessionData, ticket: Ticket) -> AsyncGenerator[ServerSentEvent, None]:
        """Wait for the gate, stream the answer, translate it for Kiswahili users, then send done (or error)."""
        yield sse("status", {"stage": "retrieved", "chunks": len(session.chunks)})
        async with aclosing(ticket.positions()) as positions:
            async for position in positions:
                if position:
                    yield sse("status", {"stage": "queued", "position": position})
        yield sse("status", {"stage": "generating"})
        start = time.perf_counter()
        try:
            prompt = build_prompt(session.question_en, [c.chunk for c in session.chunks], self.settings)
            async with aclosing(generate_stream(prompt, self.llm, self.refs)) as items:
                async for item in items:
                    if isinstance(item, GenerationResult):
                        parsed = self._store(session, item)
                    else:
                        session.answer_en += item.text
                        yield sse("token", {"text": item.text, "deltas": [asdict(d) for d in item.deltas]})
            if session.lang == "sw":
                yield sse("status", {"stage": "translating"})
                translated = await run_in_threadpool(self.language.translate_result, parsed)
                session.parsed_user = translated.sections_sw
                session.untranslated = translated.untranslated_segments
                yield self._translated(session.parsed_user)
        except Exception as exc:
            code, message = error_info(exc)
            session.status = "error"
            log.warning("generation_failed", extra={"session_id": session_id, "code": code})
            yield sse("error", {"code": code, "message": message})
            return
        finally:
            ticket.release()  # free the CPU for the next queued answer before the tail of this response is sent
        session.status = "done"
        check = session.citation_check or CitationCheck()
        log.info(
            "generation_done",
            extra={
                "session_id": session_id,
                "ms": round((time.perf_counter() - start) * 1000),
                "format_ok": parsed.format_ok,
                "citations_verified": len(check.verified),
                "citations_unmatched": len(check.unmatched),
                "untranslated_segments": len(session.untranslated),
            },
        )
        yield self._done(session, parsed)

    async def replay(self, session: SessionData) -> AsyncGenerator[ServerSentEvent, None]:
        """The finished session's events again: null, or the whole answer as one token, translation and done."""
        ui = self.ui[session.lang]
        if session.fallback or session.parsed is None:
            yield sse("null", {"message": ui["fallback"], "disclaimer": ui["disclaimer"]})
            return
        deltas = [{"section": key, "text": text} for key, text in _sections(session.parsed).items() if text]
        yield sse("token", {"text": session.answer_en, "deltas": deltas})
        if session.parsed_user is not None:
            yield self._translated(session.parsed_user)
        yield self._done(session, session.parsed)

    @staticmethod
    def _store(session: SessionData, result: GenerationResult) -> ParsedResponse:
        """Keep the finished English sections (model disclaimer removed) and the citation check on the session."""
        session.parsed = without_disclaimer(result.sections)
        session.citation_check = result.citation_check
        return session.parsed

    @staticmethod
    def _translated(parsed_user: ParsedResponse) -> ServerSentEvent:
        """The Kiswahili sections that replace the English draft."""
        return sse("translated", {"sections": _sections(parsed_user)})

    def _done(self, session: SessionData, parsed: ParsedResponse) -> ServerSentEvent:
        """Final event: localized warnings, citation check, format flag, truncated chunk ids, untranslated text."""
        ui = self.ui[session.lang]
        check = session.citation_check or CitationCheck()
        warnings = [ui["translation_note"]] if session.lang == "sw" else []
        if check.unmatched:
            warnings.append(ui["citation_warning"])
        if session.untranslated:
            warnings.append(ui["untranslated_note"])
        return sse(
            "done",
            {
                "warnings": warnings,
                "citation_check": check.model_dump(),
                "format_ok": parsed.format_ok,
                "truncated_chunks": [c.chunk.chunk_id for c in session.chunks if c.truncated],
                "untranslated": session.untranslated,
                "disclaimer": ui["disclaimer"],
            },
        )
