import json
from pathlib import Path

import numpy as np
import pytest

from backend.app.config import Settings
from backend.app.ingestion.build_index import build_indexes, main
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.sparse import SparseIndex
from backend.app.retrieval.store import ChunkStore
from backend.tests.corpus import TENANCY, corpus
from backend.tests.fakes import FakeEmbedder


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(chunks_path=tmp_path / "processed" / "chunks.json", index_dir=tmp_path / "indexes")
    ChunkStore(corpus()).save(s.chunks_path)
    return s


def _load(s: Settings) -> tuple[DenseIndex, SparseIndex]:
    corpus_hash = ChunkStore.load(s.chunks_path).corpus_hash
    dense = DenseIndex.load(s.dense_index_dir, model_name=s.embedding_model, corpus_hash=corpus_hash)
    return dense, SparseIndex.open(s.sparse_index_dir, corpus_hash=corpus_hash)


def test_build_indexes_reports_counts_and_writes_loadable_indexes(settings: Settings) -> None:
    stats = build_indexes(settings, FakeEmbedder())
    assert (stats.chunks, stats.indexed, stats.repealed) == (22, 20, 2)
    assert stats.windows > stats.indexed
    assert stats.windows_over_limit == 0
    assert stats.dense_bytes > 0 and stats.sparse_bytes > 0
    dense, sparse = _load(settings)
    assert dense.index.ntotal == stats.windows
    assert sparse.doc_count == 20


def test_windows_over_the_token_limit_are_counted(settings: Settings) -> None:
    tight = settings.model_copy(update={"embed_max_tokens": 20})
    assert build_indexes(tight, FakeEmbedder()).windows_over_limit > 0


def test_rebuild_is_idempotent_and_removes_stale_files(settings: Settings) -> None:
    build_indexes(settings, FakeEmbedder())
    dense1, sparse1 = _load(settings)
    first_meta = json.loads((settings.dense_index_dir / "meta.json").read_text(encoding="utf-8"))
    for directory in (settings.dense_index_dir, settings.sparse_index_dir):
        (directory / "stale.bin").write_bytes(b"x")
    build_indexes(settings, FakeEmbedder())
    dense2, sparse2 = _load(settings)
    n = dense1.index.ntotal
    assert np.array_equal(dense1.index.reconstruct_n(0, n), dense2.index.reconstruct_n(0, n))
    assert dense1.window_chunk_ids == dense2.window_chunk_ids
    assert sparse1.search("landlord rent", k=5) == sparse2.search("landlord rent", k=5)
    assert not (settings.dense_index_dir / "stale.bin").exists()
    assert not (settings.sparse_index_dir / "stale.bin").exists()
    second_meta = json.loads((settings.dense_index_dir / "meta.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in first_meta.items() if k != "built_at"} == {
        k: v for k, v in second_meta.items() if k != "built_at"
    }


def test_changed_corpus_makes_old_indexes_unloadable(settings: Settings) -> None:
    build_indexes(settings, FakeEmbedder())
    chunks = corpus()
    ChunkStore([*chunks[:-1], chunks[-1].model_copy(update={"text": "Edited."})]).save(settings.chunks_path)
    with pytest.raises(IndexMismatchError):
        _load(settings)


def test_main_prints_summary(settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], settings=settings, embedder=FakeEmbedder()) == 0
    out = capsys.readouterr().out
    assert "22 chunks (20 indexed, 2 repealed skipped)" in out
    assert "dense" in out and "sparse" in out and "MB" in out
    assert TENANCY not in out


def test_main_missing_chunks_file_exits_2(settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    settings.chunks_path.unlink()
    assert main([], settings=settings, embedder=FakeEmbedder()) == 2
    assert "build_corpus" in capsys.readouterr().err


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps([{"chunk_id": "Bad Id"}]),
        json.dumps([corpus()[0].model_dump()] * 2),
        json.dumps([c.model_dump() for c in corpus() if c.repealed]),
    ],
)
def test_main_invalid_chunks_file_exits_1(settings: Settings, capsys: pytest.CaptureFixture[str], payload: str) -> None:
    settings.chunks_path.write_text(payload, encoding="utf-8")
    assert main([], settings=settings, embedder=FakeEmbedder()) == 1
    assert "invalid" in capsys.readouterr().err
    assert not settings.index_dir.exists()
