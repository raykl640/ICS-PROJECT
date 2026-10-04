"""Cross-encoder reranking (ARCHITECTURE.md §6): score top_n candidates jointly with the question, keep the best few."""

import threading
from collections.abc import Sequence
from typing import Any, Protocol

from backend.app.interfaces import CrossEncoderLike
from backend.app.models import LegalChunk, RetrievedChunk
from backend.app.retrieval.embedder import hf_offline


class _PairModel(Protocol):
    """The part of sentence_transformers.CrossEncoder used here."""

    def predict(self, pairs: list[tuple[str, str]], **kwargs: Any) -> Sequence[float]: ...


_MODELS: dict[tuple[str, int], _PairModel] = {}
_MODELS_LOCK = threading.Lock()


def _build_cross_encoder(model_name: str, max_length: int) -> _PairModel:
    """Load a CPU CrossEncoder that returns raw logits (Identity activation), cache-only when offline."""
    import torch  # heavy imports, only when a real model is used
    from sentence_transformers import CrossEncoder

    model: _PairModel = CrossEncoder(
        model_name,
        max_length=max_length,
        device="cpu",
        local_files_only=hf_offline(),
        activation_fn=torch.nn.Identity(),
    )
    return model


def _shared_model(model_name: str, max_length: int) -> _PairModel:
    """One loaded model per (name, max_length) per process, loaded on first use."""
    key = (model_name, max_length)
    with _MODELS_LOCK:
        if key not in _MODELS:
            _MODELS[key] = _build_cross_encoder(model_name, max_length)
        return _MODELS[key]


class CEReranker:
    """sentence-transformers cross-encoder behind CrossEncoderLike; the model loads lazily and is shared."""

    def __init__(self, model_name: str, max_length: int, batch_size: int) -> None:
        self._model_name = model_name
        self._max_length = max_length
        self._batch_size = batch_size

    def score(self, query: str, docs: list[str]) -> list[float]:
        """Raw relevance logits, one per doc; inputs beyond max_length tokens are truncated by the tokenizer."""
        if not docs:
            return []
        model = _shared_model(self._model_name, self._max_length)
        scores = model.predict([(query, doc) for doc in docs], batch_size=self._batch_size, show_progress_bar=False)
        return [float(s) for s in scores]

    def warmup(self) -> None:
        """Load the model and run one pair so the first real query is not slowed by lazy initialisation."""
        self.score("warm up", ["warm up"])


def pair_text(chunk: LegalChunk) -> str:
    """'{act} {unit} {num} {title}: {text}'; a schedule's section_num already names the unit."""
    unit = "" if chunk.unit_type == "schedule" else f"{chunk.unit_type.capitalize()} "
    return f"{chunk.act} {unit}{chunk.section_num} {chunk.section_title}: {chunk.text}"


def rerank(model: CrossEncoderLike, question: str, candidates: list[RetrievedChunk], top: int) -> list[RetrievedChunk]:
    """Score every candidate, sort by score descending (ties keep RRF order) and return the first `top`."""
    if not candidates:
        return []
    scores = model.score(question, [pair_text(c.chunk) for c in candidates])
    if len(scores) != len(candidates):
        raise ValueError(f"reranker returned {len(scores)} scores for {len(candidates)} candidates")
    order = sorted(range(len(candidates)), key=lambda i: -scores[i])[:top]  # stable: ties keep RRF order
    return [candidates[i].model_copy(update={"rerank_score": scores[i]}) for i in order]


def is_confident(scored: list[RetrievedChunk], threshold: float, min_chunks: int) -> bool:
    """True iff at least min_chunks chunks have rerank_score >= threshold (inclusive)."""
    return sum(c.rerank_score is not None and c.rerank_score >= threshold for c in scored) >= min_chunks
