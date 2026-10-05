"""Retrieval front half (ARCHITECTURE.md §5-7.5): hybrid candidates -> cross-encoder top-k -> null-response decision.

The fallback is used only when the question is out of scope (retrieval/scope.py) and the cross-encoder is not confident
either, or when too few candidates exist at all (DEVIATIONS D21). It has no LLM dependency: a null result carries no
chunks, so nothing downstream can generate from it.
"""

import time
from dataclasses import dataclass
from typing import Protocol

from backend.app.config import Settings
from backend.app.interfaces import CrossEncoderLike, Embedder
from backend.app.models import RetrievedChunk
from backend.app.retrieval.embedder import STEmbedder
from backend.app.retrieval.hybrid import RetrievalResult, load_retriever
from backend.app.retrieval.reranker import CEReranker, is_confident, rerank
from backend.app.retrieval.scope import load_scope


class CandidateSource(Protocol):
    """Anything that yields fused top_n candidates for a question (HybridRetriever in production)."""

    def retrieve(self, question: str) -> RetrievalResult:
        """Fused candidates with per-stage timings."""
        ...


class ScopeCheck(Protocol):
    """Semantic in-scope margin for a question (ScopeClassifier in production)."""

    def margin(self, question: str) -> float:
        """Higher means closer to the corpus's subject matter; compared with settings.scope_margin."""
        ...


@dataclass(frozen=True)
class ContextDebug:
    """Ids, scores and timings for eval/benchmarks; never chunk or question text."""

    acts: list[str] | None
    widened: bool
    candidates: int
    scores: list[tuple[str, float]]
    scope_margin: float
    timings_ms: dict[str, float]


@dataclass(frozen=True)
class ContextResult:
    """Chunks for generation (empty when null) and whether the fixed fallback must be used instead of the LLM."""

    chunks: list[RetrievedChunk]
    null: bool
    debug: ContextDebug


class ContextPipeline:
    """Retrieves, reranks and decides whether the context is confident enough to generate from."""

    def __init__(
        self, retriever: CandidateSource, reranker: CrossEncoderLike, scope: ScopeCheck, settings: Settings
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._scope = scope
        self._settings = settings

    def retrieve_context(self, question_en: str) -> ContextResult:
        """Top rerank_top chunks, or null=True with no chunks when neither the scope check nor the reranker vouches."""
        start = time.perf_counter()
        retrieved = self._retriever.retrieve(question_en)
        rerank_start = time.perf_counter()
        top = rerank(self._reranker, question_en, retrieved.candidates, self._settings.rerank_top)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000
        scope_start = time.perf_counter()
        margin = self._scope.margin(question_en)
        scope_ms = (time.perf_counter() - scope_start) * 1000
        null = not self._answerable(top, margin)
        debug = ContextDebug(
            acts=retrieved.acts,
            widened=retrieved.widened,
            candidates=len(retrieved.candidates),
            scores=[(c.chunk.chunk_id, c.rerank_score) for c in top if c.rerank_score is not None],
            scope_margin=margin,
            timings_ms=retrieved.timings_ms
            | {"rerank": rerank_ms, "scope": scope_ms, "total": (time.perf_counter() - start) * 1000},
        )
        return ContextResult(chunks=[] if null else top, null=null, debug=debug)

    def _answerable(self, top: list[RetrievedChunk], margin: float) -> bool:
        """Enough candidates, and either an in-scope question or a confident reranker."""
        settings = self._settings
        if len(top) < settings.min_confident_chunks:
            return False
        in_scope = margin >= settings.scope_margin
        return in_scope or is_confident(top, settings.relevance_threshold, settings.min_confident_chunks)


def load_pipeline(
    settings: Settings, embedder: Embedder | None = None, reranker: CrossEncoderLike | None = None
) -> ContextPipeline:
    """Load the indexes (IndexMismatchError if stale or missing) and wire the production models unless given them."""
    embedder = embedder or STEmbedder(settings.embedding_model, settings.embed_batch_size)
    retriever = load_retriever(settings, embedder)
    reranker = reranker or CEReranker(
        settings.reranker_model, settings.reranker_max_length, settings.reranker_batch_size
    )
    return ContextPipeline(retriever, reranker, load_scope(settings, embedder), settings)
