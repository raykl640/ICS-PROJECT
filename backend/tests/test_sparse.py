from pathlib import Path

import pytest

from backend.app.retrieval.meta import REBUILD_COMMAND, IndexMismatchError
from backend.app.retrieval.sparse import SparseIndex, sanitize
from backend.app.retrieval.store import ChunkStore
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, TENANCY, corpus, make_chunk

STORE = ChunkStore(corpus())


@pytest.fixture(scope="module")
def index(tmp_path_factory: pytest.TempPathFactory) -> SparseIndex:
    directory = tmp_path_factory.mktemp("sparse")
    return SparseIndex.build(STORE.indexable(), directory, corpus_hash=STORE.corpus_hash)


def _ids(hits: list[tuple[str, float]]) -> list[str]:
    return [cid for cid, _ in hits]


def test_repealed_chunks_are_not_indexed(index: SparseIndex) -> None:
    assert index.doc_count == 20
    assert index.meta.kind == "sparse"
    assert (index.meta.chunks, index.meta.entries) == (20, 20)
    assert not {f"{EMPLOYMENT}-7", f"{TENANCY}-6"} & set(_ids(index.search("repealed act", k=50)))


def test_exact_phrase_ranks_its_chunk_first(index: SparseIndex) -> None:
    hits = index.search("twenty one days of paid annual leave", k=5)
    assert _ids(hits)[0] == f"{EMPLOYMENT}-5"
    assert [s for _, s in hits] == sorted((s for _, s in hits), reverse=True)


def test_stemming_matches_inflected_forms(index: SparseIndex) -> None:
    assert _ids(index.search("evicted", k=3))[0] == f"{TENANCY}-3"


def test_exact_section_number(index: SparseIndex) -> None:
    assert _ids(index.search("section 8", k=3))[0] == f"{EMPLOYMENT}-8"
    assert _ids(index.search("section 41", k=1, acts={TENANCY})) == [f"{TENANCY}-41"]


def test_title_match_outranks_body_only_match(tmp_path: Path) -> None:
    in_title = make_chunk(TENANCY, "1", "Tribunal", "General provisions apply here.")
    in_text = make_chunk(TENANCY, "2", "General", "Tribunal provisions apply here.")
    small = SparseIndex.build([in_text, in_title], tmp_path, corpus_hash="0" * 64)
    assert _ids(small.search("tribunal", k=2)) == [in_title.chunk_id, in_text.chunk_id]


def test_act_filter_restricts_results(index: SparseIndex) -> None:
    hits = index.search("notice", k=10, acts={TENANCY})
    assert _ids(hits) == [f"{TENANCY}-2"]
    both = _ids(index.search("right person", k=10, acts={CONSTITUTION, TENANCY}))
    assert both and all(cid.startswith((CONSTITUTION, TENANCY)) for cid in both)


def test_empty_acts_means_full_corpus(index: SparseIndex) -> None:
    assert len(index.search("notice", k=10, acts=set())) == 2


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ('AND OR * ( " :', "and or"),
        ("text:landlord AND NOT tenant*", "text landlord and not tenant"),
        ('"evict" OR (rent^2 ~ [a TO b]) {x} s.41(2)!', "evict or rent 2 a to b x s 41 2"),
        ("  ", ""),
    ],
)
def test_sanitize_strips_query_syntax(raw: str, clean: str) -> None:
    assert sanitize(raw) == clean


@pytest.mark.parametrize(
    "query", ['AND OR * ( " :', "NOT", "*", '"', "(", ":", "", "landlord AND", "OR tenant", 'evict" (rent']
)
def test_hostile_queries_never_raise(index: SparseIndex, query: str) -> None:
    assert isinstance(index.search(query, k=5), list)


def test_query_with_only_syntax_or_stopwords_returns_nothing(index: SparseIndex) -> None:
    assert index.search('AND OR * ( " :', k=5) == []
    assert index.search("", k=5) == []


def test_operators_are_treated_as_plain_words(index: SparseIndex) -> None:
    assert f"{TENANCY}-1" in _ids(index.search("landlord NOT tenant", k=10))


def test_open_roundtrip_and_mismatch(index: SparseIndex, tmp_path: Path) -> None:
    reopened = SparseIndex.open(index.directory, corpus_hash=STORE.corpus_hash)
    assert reopened.search("eviction", k=5) == index.search("eviction", k=5)
    assert reopened.meta == index.meta
    with pytest.raises(IndexMismatchError, match=REBUILD_COMMAND):
        SparseIndex.open(index.directory, corpus_hash="f" * 64)
    with pytest.raises(IndexMismatchError, match=REBUILD_COMMAND):
        SparseIndex.open(tmp_path / "nothing", corpus_hash=STORE.corpus_hash)


def test_build_wipes_previous_contents(tmp_path: Path) -> None:
    (tmp_path / "stale.seg").write_text("old", encoding="utf-8")
    first = SparseIndex.build(STORE.indexable(), tmp_path, corpus_hash=STORE.corpus_hash)
    second = SparseIndex.build(STORE.indexable(), tmp_path, corpus_hash=STORE.corpus_hash)
    assert not (tmp_path / "stale.seg").exists()
    assert second.doc_count == 20
    assert second.search("rent notice", k=5) == first.search("rent notice", k=5)
