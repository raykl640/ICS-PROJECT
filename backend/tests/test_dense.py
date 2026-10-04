from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.meta import REBUILD_COMMAND, IndexMismatchError
from backend.app.retrieval.store import ChunkStore
from backend.app.retrieval.windows import WindowSpec, make_windows
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, LONG_TAIL, TENANCY, corpus
from backend.tests.fakes import FakeEmbedder

SPEC = WindowSpec(split_over=200, words=180, stride=120)
MODEL = "fake-model"
EMB = FakeEmbedder()
STORE = ChunkStore(corpus())
LONG_ID = f"{EMPLOYMENT}-41"


@pytest.fixture(scope="module")
def index() -> DenseIndex:
    return DenseIndex.build(STORE.indexable(), EMB, spec=SPEC, model_name=MODEL, corpus_hash=STORE.corpus_hash)


def _query(text: str) -> npt.NDArray[np.float32]:
    return np.asarray(EMB.encode([text])[0], dtype=np.float32)


def test_build_records_meta_and_one_vector_per_window(index: DenseIndex) -> None:
    windows = sum(len(make_windows(c, SPEC)) for c in STORE.indexable())
    assert index.index.ntotal == windows == len(index.window_chunk_ids) == len(index.window_act_slugs)
    assert windows > len(STORE.indexable())
    meta = index.meta
    assert (meta.kind, meta.model, meta.dim, meta.corpus_hash) == ("dense", MODEL, 384, STORE.corpus_hash)
    assert (meta.chunks, meta.entries) == (20, windows)


def test_repealed_chunks_are_not_indexed(index: DenseIndex) -> None:
    repealed = {c.chunk_id for c in STORE.all() if c.repealed}
    assert repealed
    assert not repealed & set(index.window_chunk_ids)


def test_windows_map_back_to_their_parent_chunk(index: DenseIndex) -> None:
    windows = make_windows(STORE.get([LONG_ID])[0], SPEC)
    assert index.window_chunk_ids.count(LONG_ID) == len(windows) > 1
    for window in windows:
        [(chunk_id, distance)] = index.search(_query(window), k=1)
        assert chunk_id == LONG_ID
        assert distance == pytest.approx(0.0, abs=1e-5)


def test_parent_score_is_the_best_window_and_parents_are_unique(index: DenseIndex) -> None:
    query = _query("employer records of service " + LONG_TAIL)
    window_vecs = EMB.encode(make_windows(STORE.get([LONG_ID])[0], SPEC))
    best = float(np.min(np.sum((window_vecs - query) ** 2, axis=1)))
    hits = index.search(query, k=20)
    ids = [cid for cid, _ in hits]
    assert len(ids) == len(set(ids)) == 20
    assert dict(hits)[LONG_ID] == pytest.approx(best, abs=1e-5)
    assert [d for _, d in hits] == sorted(d for _, d in hits)


def test_act_filter_restricts_results(index: DenseIndex) -> None:
    hits = index.search(_query("landlord notice rent"), k=5, acts={EMPLOYMENT, CONSTITUTION})
    assert hits
    assert all(not cid.startswith(TENANCY) for cid, _ in hits)


def test_filter_returns_what_exists_when_fewer_than_k(index: DenseIndex) -> None:
    hits = index.search(_query("tenant"), k=50, acts={TENANCY})
    assert len(hits) == 6
    assert {cid.rsplit("-", 1)[0] for cid, _ in hits} == {TENANCY}


def test_empty_acts_means_full_corpus_and_unknown_act_means_nothing(index: DenseIndex) -> None:
    assert len(index.search(_query("tenant"), k=50, acts=set())) == 20
    assert index.search(_query("tenant"), k=5, acts={"no-such-act"}) == []


def test_query_dimension_is_checked(index: DenseIndex) -> None:
    with pytest.raises(ValueError, match="dimension"):
        index.search(np.zeros(3, dtype=np.float32), k=5)


def test_save_load_roundtrip(index: DenseIndex, tmp_path: Path) -> None:
    index.save(tmp_path)
    loaded = DenseIndex.load(tmp_path, model_name=MODEL, corpus_hash=STORE.corpus_hash)
    n = index.index.ntotal
    assert np.array_equal(loaded.index.reconstruct_n(0, n), index.index.reconstruct_n(0, n))
    assert loaded.window_chunk_ids == index.window_chunk_ids
    assert loaded.window_act_slugs == index.window_act_slugs
    assert loaded.meta == index.meta
    query = _query("eviction of a tenant")
    assert loaded.search(query, k=5, acts={TENANCY}) == index.search(query, k=5, acts={TENANCY})


@pytest.mark.parametrize(("model", "corpus_hash"), [("other-model", None), (MODEL, "f" * 64)])
def test_load_rejects_model_or_corpus_mismatch(
    index: DenseIndex, tmp_path: Path, model: str, corpus_hash: str | None
) -> None:
    index.save(tmp_path)
    with pytest.raises(IndexMismatchError, match=REBUILD_COMMAND):
        DenseIndex.load(tmp_path, model_name=model, corpus_hash=corpus_hash or STORE.corpus_hash)


def test_load_of_a_missing_index_says_how_to_build_it(tmp_path: Path) -> None:
    with pytest.raises(IndexMismatchError, match=REBUILD_COMMAND):
        DenseIndex.load(tmp_path / "nothing", model_name=MODEL, corpus_hash=STORE.corpus_hash)


def test_build_rejects_an_empty_corpus() -> None:
    with pytest.raises(ValueError, match="no chunks"):
        DenseIndex.build([], EMB, spec=SPEC, model_name=MODEL, corpus_hash=STORE.corpus_hash)
