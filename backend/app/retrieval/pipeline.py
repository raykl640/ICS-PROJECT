"""Retrieval front half (ARCHITECTURE.md §5-7.5): hybrid candidates -> cross-encoder top-k -> null-response decision.

It has no LLM dependency: a null result carries no chunks, so nothing downstream can generate from it.
"""

import time
from dataclasses import dataclass
from typing import Protocol

from backend.app.config import Settings
from backend.app.interfaces import CrossEncoderLike, Embedder
from backend.app.models import RetrievedChunk
from backend.app.retrieval.hybrid import RetrievalResult, load_retriever
from backend.app.retrieval.reranker import CEReranker, is_confident, rerank


class CandidateSource(Protocol):
    """Anything that yields fused top_n candidates for a question (HybridRetriever in production)."""

    def retrieve(self, question: str) -> RetrievalResult:
        """Fused candidates with per-stage timings."""
        ...


@dataclass(frozen=True)
class ContextDebug:
    """Ids, scores and timings for eval/benchmarks; never chunk or question text."""

    acts: list[str] | None
    widened: bool
    candidates: int
    scores: list[tuple[str, float]]
    timings_ms: dict[str, float]


@dataclass(frozen=True)
class ContextResult:
    """Chunks for generation (empty when null) and whether the fixed fallback must be used instead of the LLM."""

    chunks: list[RetrievedChunk]
    null: bool
    debug: ContextDebug


class ContextPipeline:
    """Retrieves, reranks and decides whether the context is confident enough to generate from."""

    def __init__(self, retriever: CandidateSource, reranker: CrossEncoderLike, settings: Settings) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._settings = settings

    def retrieve_context(self, question_en: str) -> ContextResult:
        """Top rerank_top chunks, or null=True with no chunks if < min_confident_chunks reach relevance_threshold."""
        start = time.perf_counter()
        retrieved = self._retriever.retrieve(question_en)
        rerank_start = time.perf_counter()
        top = rerank(self._reranker, question_en, retrieved.candidates, self._settings.rerank_top)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000
        settings = self._settings
        null = not is_confident(top, settings.relevance_threshold, settings.min_confident_chunks)
        debug = ContextDebug(
            acts=retrieved.acts,
            widened=retrieved.widened,
            candidates=len(retrieved.candidates),
            scores=[(c.chunk.chunk_id, c.rerank_score) for c in top if c.rerank_score is not None],
            timings_ms=retrieved.timings_ms | {"rerank": rerank_ms, "total": (time.perf_counter() - start) * 1000},
        )
        return ContextResult(chunks=[] if null else top, null=null, debug=debug)


def load_pipeline(
    settings: Settings, embedder: Embedder | None = None, reranker: CrossEncoderLike | None = None
) -> ContextPipeline:
    """Load the indexes (IndexMismatchError if stale or missing) and wire the production reranker unless given one."""
    retriever = load_retriever(settings, embedder)
    reranker = reranker or CEReranker(
        settings.reranker_model, settings.reranker_max_length, settings.reranker_batch_size
    )
    return ContextPipeline(retriever, reranker, settings)
