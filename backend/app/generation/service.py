"""Run one generation: stream tokens with their section deltas, then a final result with sections and citation check."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass

from backend.app.generation.citations import check_citations
from backend.app.generation.parse import SectionDelta, SectionSplitter
from backend.app.generation.prompt import PromptBuild
from backend.app.interfaces import LLMClient
from backend.app.models import CitationCheck, ParsedResponse
from backend.app.retrieval.refs import RefExtractor


@dataclass(frozen=True)
class TokenEvent:
    """One streamed token and the section text it completed (may be empty while a header is buffered)."""

    text: str
    deltas: tuple[SectionDelta, ...]


@dataclass(frozen=True)
class GenerationResult:
    """The finished answer: full text, its sections, citations checked against the prompt's chunks."""

    full_text: str
    sections: ParsedResponse
    citation_check: CitationCheck
    truncated: bool


async def generate_stream(
    prompt: PromptBuild, llm: LLMClient, refs: RefExtractor | None = None
) -> AsyncGenerator[TokenEvent | GenerationResult, None]:
    """Yield a TokenEvent per LLM token, then one GenerationResult; LLM errors propagate unchanged.

    Closing this generator early closes the LLM stream too (which stops Ollama).
    """
    splitter = SectionSplitter()
    parts: list[str] = []
    async with aclosing(llm.stream(prompt.text)) as tokens:
        async for token in tokens:
            parts.append(token)
            yield TokenEvent(token, tuple(splitter.feed(token)))
    full_text = "".join(parts)
    yield GenerationResult(
        full_text=full_text,
        sections=splitter.finalize(),
        citation_check=check_citations(full_text, prompt.chunks, refs),
        truncated=prompt.truncated,
    )
