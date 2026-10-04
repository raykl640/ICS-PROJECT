"""Hybrid retrieval (ARCHITECTURE.md §5): route -> dense + sparse in parallel -> RRF -> top_n candidates.

CLI: python -m backend.app.retrieval.hybrid "question" [--mode hybrid|dense|sparse]
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from backend.app.config import Settings, get_settings
from backend.app.interfaces import Embedder
from backend.app.models import RetrievedChunk
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.embedder import STEmbedder
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.router import Router
from backend.app.retrieval.rrf import rrf
from backend.app.retrieval.sparse import SparseIndex
from backend.app.retrieval.store import ChunkStore


@dataclass(frozen=True)
class RetrievalResult:
    """Fused candidates plus routing and timing details for evaluation/debugging (never shown to users)."""

    candidates: list[RetrievedChunk]
    acts: list[str] | None
    widened: bool
    timings_ms: dict[str, float]
    dense_only_ids: list[str]
    sparse_only_ids: list[str]


@dataclass(frozen=True)
class _Leg:
    """One ranked list from one index."""

    name: str
    ids: list[str]
    widened: bool
    ms: float


def _ms_since(start: float) -> float:
    """Elapsed milliseconds since a perf_counter reading."""
    return (time.perf_counter() - start) * 1000


class HybridRetriever:
    """Routes a question, searches the dense and sparse indexes, and fuses their rankings with RRF."""

    def __init__(
        self,
        embedder: Embedder,
        dense: DenseIndex,
        sparse: SparseIndex,
        store: ChunkStore,
        router: Router,
        settings: Settings,
    ) -> None:
        self._embedder = embedder
        self._dense = dense
        self._sparse = sparse
        self._store = store
        self._router = router
        self._settings = settings

    def retrieve(self, question: str) -> RetrievalResult:
        """Top-n hybrid candidates; the dense and sparse searches run concurrently."""
        start = time.perf_counter()
        acts, route_ms = self._route(question)
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="retrieve") as pool:
            dense = pool.submit(self._dense_leg, question, acts)
            sparse = pool.submit(self._sparse_leg, question, acts)
            legs = [dense.result(), sparse.result()]
        return self._fuse(legs, acts, route_ms, start)

    def retrieve_dense_only(self, question: str) -> RetrievalResult:
        """FAISS-only baseline (same routing and widening), ranked by RRF over the single list."""
        return self._single(question, self._dense_leg)

    def retrieve_sparse_only(self, question: str) -> RetrievalResult:
        """BM25-only baseline (same routing, widening and reference injection)."""
        return self._single(question, self._sparse_leg)

    def _single(self, question: str, leg: Callable[[str, list[str] | None], _Leg]) -> RetrievalResult:
        start = time.perf_counter()
        acts, route_ms = self._route(question)
        return self._fuse([leg(question, acts)], acts, route_ms, start)

    def _route(self, question: str) -> tuple[list[str] | None, float]:
        start = time.perf_counter()
        return self._router.route(question), _ms_since(start)

    def _dense_leg(self, question: str, acts: list[str] | None) -> _Leg:
        """Dense top-k within the routed Acts, rerun over the full corpus if too few hits."""
        start = time.perf_counter()
        vector = self._embedder.encode([question])[0]
        k = self._settings.dense_k
        hits = self._dense.search(vector, k, acts)
        widened = bool(acts) and len(hits) < self._settings.min_filtered_hits
        if widened:
            hits = self._dense.search(vector, k)
        return _Leg("dense", [chunk_id for chunk_id, _ in hits], widened, _ms_since(start))

    def _sparse_leg(self, question: str, acts: list[str] | None) -> _Leg:
        """BM25 top-k with the same widening rule; explicitly referenced chunks are put first."""
        start = time.perf_counter()
        k = self._settings.sparse_k
        hits = self._sparse.search(question, k, acts)
        widened = bool(acts) and len(hits) < self._settings.min_filtered_hits
        if widened:
            hits = self._sparse.search(question, k)
        ids = list(dict.fromkeys([*self._referenced_ids(question, acts), *(cid for cid, _ in hits)]))[:k]
        return _Leg("sparse", ids, widened, _ms_since(start))

    def _referenced_ids(self, question: str, acts: list[str] | None) -> list[str]:
        """Indexed chunks the question cites exactly; a bare 'section N' resolves within the routed Acts."""
        ids = []
        for ref in self._router.refs.extract_refs(question):
            for act in [ref.act] if ref.act else acts or []:
                chunk_id = f"{act}-{ref.num}"
                if chunk_id in self._store:
                    chunk = self._store.get([chunk_id])[0]
                    if chunk.unit_type == ref.unit and not chunk.repealed:
                        ids.append(chunk_id)
        return ids

    def _fuse(self, legs: Sequence[_Leg], acts: list[str] | None, route_ms: float, start: float) -> RetrievalResult:
        """RRF over the legs, cut to top_n, joined with full chunks from the store."""
        fuse_start = time.perf_counter()
        fused = rrf(*(leg.ids for leg in legs), k=self._settings.rrf_k)[: self._settings.top_n]
        chunks = self._store.get(f.chunk_id for f in fused)
        names = [leg.name for leg in legs]
        candidates = [
            RetrievedChunk(
                chunk=chunk,
                dense_rank=f.ranks[names.index("dense")] if "dense" in names else None,
                sparse_rank=f.ranks[names.index("sparse")] if "sparse" in names else None,
                rrf_score=f.score,
            )
            for f, chunk in zip(fused, chunks, strict=True)
        ]
        only = {leg.name: [i for i in leg.ids if all(i not in o.ids for o in legs if o is not leg)] for leg in legs}
        timings = {"route": route_ms, **{leg.name: leg.ms for leg in legs}, "fuse": _ms_since(fuse_start)}
        return RetrievalResult(
            candidates=candidates,
            acts=acts,
            widened=any(leg.widened for leg in legs),
            timings_ms=timings | {"total": _ms_since(start)},
            dense_only_ids=only.get("dense", []),
            sparse_only_ids=only.get("sparse", []),
        )


def load_retriever(settings: Settings, embedder: Embedder | None = None) -> HybridRetriever:
    """Load the store and both indexes (IndexMismatchError if stale or missing) and build the retriever."""
    store = ChunkStore.load(settings.chunks_path)
    dense = DenseIndex.load(
        settings.dense_index_dir, model_name=settings.embedding_model, corpus_hash=store.corpus_hash
    )
    sparse = SparseIndex.open(settings.sparse_index_dir, corpus_hash=store.corpus_hash)
    embedder = embedder or STEmbedder(settings.embedding_model, settings.embed_batch_size)
    return HybridRetriever(embedder, dense, sparse, store, Router.from_settings(settings), settings)


def render(result: RetrievalResult) -> str:
    """Candidate table with per-list ranks (ids and titles only, no chunk text)."""
    acts = ", ".join(result.acts) if result.acts else "all"
    timings = " ".join(f"{name}={ms:.0f}ms" for name, ms in result.timings_ms.items())
    lines = [f"acts: {acts}{' (widened)' if result.widened else ''}", f"timings: {timings}"]
    for n, c in enumerate(result.candidates, start=1):
        dense, sparse = c.dense_rank or "-", c.sparse_rank or "-"
        title = c.chunk.section_title
        lines.append(
            f"{n:2d}. rrf={c.rrf_score:.4f} dense={dense!s:>2} sparse={sparse!s:>2}  {c.chunk.chunk_id} | {title}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, settings: Settings | None = None, embedder: Embedder | None = None) -> int:
    """CLI. Exit 0 on success, 2 when chunks.json or the indexes are missing or stale."""
    parser = argparse.ArgumentParser(description="Print hybrid retrieval candidates for a question.")
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["hybrid", "dense", "sparse"], default="hybrid")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    try:
        retriever = load_retriever(settings, embedder)
    except (IndexMismatchError, FileNotFoundError) as err:
        print(err, file=sys.stderr)
        return 2
    run = {
        "hybrid": retriever.retrieve,
        "dense": retriever.retrieve_dense_only,
        "sparse": retriever.retrieve_sparse_only,
    }[args.mode]
    print(render(run(args.question)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
