"""Build the FAISS (dense) and Whoosh (BM25) indexes and refs.json from data/processed/chunks.json."""

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from backend.app.config import Settings, get_settings
from backend.app.interfaces import Embedder
from backend.app.laws.xrefs import build_cross_refs, save_cross_refs
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.embedder import STEmbedder
from backend.app.retrieval.meta import dir_bytes
from backend.app.retrieval.refs import RefExtractor
from backend.app.retrieval.router import Router
from backend.app.retrieval.sparse import SparseIndex
from backend.app.retrieval.store import ChunkStore
from backend.app.retrieval.windows import WindowSpec, make_windows

_MB = 1024 * 1024


@dataclass(frozen=True)
class IndexBuild:
    """Counts, sizes and timings of one index build."""

    chunks: int
    indexed: int
    repealed: int
    windows: int
    windows_over_limit: int
    dense_bytes: int
    sparse_bytes: int
    dense_s: float
    sparse_s: float
    refs_resolved: int
    refs_unresolved: int
    refs_citing: int


def load_indexable(settings: Settings) -> ChunkStore:
    """Load and validate chunks.json; ValueError if it has nothing to index."""
    store = ChunkStore.load(settings.chunks_path)
    if not store.indexable():
        raise ValueError("no non-repealed chunks")
    return store


def build_indexes(settings: Settings, embedder: Embedder, extractor: RefExtractor | None = None) -> IndexBuild:
    """Validate chunks.json, then rebuild both indexes and refs.json (refs default: the configured Acts' extractor)."""
    store = load_indexable(settings)
    chunks = store.indexable()
    spec = WindowSpec.from_settings(settings)
    windows = [w for c in chunks for w in make_windows(c, spec)]
    start = time.perf_counter()
    dense = DenseIndex.build(
        chunks, embedder, spec=spec, model_name=settings.embedding_model, corpus_hash=store.corpus_hash
    )
    dense.save(settings.dense_index_dir)
    dense_done = time.perf_counter()
    SparseIndex.build(chunks, settings.sparse_index_dir, corpus_hash=store.corpus_hash)
    sparse_done = time.perf_counter()
    refs = build_cross_refs(store, extractor or Router.from_settings(settings).refs)
    save_cross_refs(refs, settings.refs_path)
    return IndexBuild(
        chunks=len(store),
        indexed=len(chunks),
        repealed=len(store) - len(chunks),
        windows=len(windows),
        windows_over_limit=sum(embedder.count_tokens(w) > settings.embed_max_tokens for w in windows),
        dense_bytes=dir_bytes(settings.dense_index_dir),
        sparse_bytes=dir_bytes(settings.sparse_index_dir),
        dense_s=dense_done - start,
        sparse_s=sparse_done - dense_done,
        refs_resolved=refs.resolved,
        refs_unresolved=refs.unresolved,
        refs_citing=len(refs.out),
    )


def render(stats: IndexBuild, settings: Settings) -> str:
    """Human-readable build summary (counts only, no chunk content)."""
    return "\n".join(
        [
            f"{stats.chunks} chunks ({stats.indexed} indexed, {stats.repealed} repealed skipped)",
            f"dense  {stats.windows} windows ({stats.windows_over_limit} over {settings.embed_max_tokens} tokens), "
            f"{stats.dense_bytes / _MB:.1f} MB, {stats.dense_s:.1f} s -> {settings.dense_index_dir}",
            f"sparse {stats.indexed} docs, {stats.sparse_bytes / _MB:.1f} MB, {stats.sparse_s:.1f} s "
            f"-> {settings.sparse_index_dir}",
            f"refs   {stats.refs_resolved} linked + {stats.refs_unresolved} unlinked in {stats.refs_citing} sections "
            f"-> {settings.refs_path}",
        ]
    )


def describe(err: ValueError) -> str:
    """Error summary without echoing chunk text (pydantic messages include input values)."""
    if isinstance(err, ValidationError):
        first = err.errors()[0]
        return f"{err.error_count()} validation error(s); first at {first['loc']}: {first['msg']}"
    return str(err)


def main(argv: Sequence[str] | None = None, settings: Settings | None = None, embedder: Embedder | None = None) -> int:
    """CLI. Exit 0 on success, 1 when chunks.json is invalid, 2 when it is missing."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    settings = settings or get_settings()
    try:
        load_indexable(settings)
    except FileNotFoundError:
        print(f"{settings.chunks_path} not found; run: python -m backend.app.ingestion.build_corpus", file=sys.stderr)
        return 2
    except ValueError as err:
        print(f"invalid {settings.chunks_path}: {describe(err)}", file=sys.stderr)
        return 1
    embedder = embedder or STEmbedder(settings.embedding_model, settings.embed_batch_size)
    print(render(build_indexes(settings, embedder), settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
