from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.ingestion.build_index import build_indexes
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.hybrid import HybridRetriever, load_retriever, main
from backend.app.retrieval.rrf import rrf
from backend.app.retrieval.sparse import SparseIndex
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, TENANCY
from backend.tests.fake_pipeline import EMB, STORE, build_parts, fake_retriever


@pytest.fixture(scope="module")
def parts(tmp_path_factory: pytest.TempPathFactory) -> tuple[DenseIndex, SparseIndex]:
    return build_parts(tmp_path_factory.mktemp("sp"))


def _retriever(parts: tuple[DenseIndex, SparseIndex], **overrides: int) -> HybridRetriever:
    settings = Settings(top_n=10, **overrides)  # type: ignore[arg-type]
    return fake_retriever(parts, settings)


def test_hybrid_equals_rrf_of_the_single_legs(parts: tuple[DenseIndex, SparseIndex]) -> None:
    retriever = _retriever(parts)
    query = "my employer fired me and did not pay wages"
    hybrid = retriever.retrieve(query)
    dense = retriever.retrieve_dense_only(query)
    sparse = retriever.retrieve_sparse_only(query)
    expected = rrf([c.chunk.chunk_id for c in dense.candidates], [c.chunk.chunk_id for c in sparse.candidates], k=60)[
        :10
    ]
    assert [(c.chunk.chunk_id, c.dense_rank, c.sparse_rank) for c in hybrid.candidates] == [
        (f.chunk_id, f.ranks[0], f.ranks[1]) for f in expected
    ]
    assert [c.rrf_score for c in hybrid.candidates] == pytest.approx([f.score for f in expected])
    assert hybrid.acts == [EMPLOYMENT, CONSTITUTION]


def test_repeated_calls_are_identical(parts: tuple[DenseIndex, SparseIndex]) -> None:
    retriever = _retriever(parts)
    first = retriever.retrieve("landlord evict tenant")
    for _ in range(5):
        again = retriever.retrieve("landlord evict tenant")
        assert again.candidates == first.candidates


def test_candidates_are_capped_at_top_n_and_carry_full_chunks(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts).retrieve("tenant rights")
    assert len(result.candidates) == 10
    assert all(c.chunk.text and not c.chunk.repealed for c in result.candidates)
    scores = [c.rrf_score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)


def test_routing_filters_both_legs(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts, min_filtered_hits=1).retrieve("my landlord wants to evict me")
    assert result.acts == [TENANCY, CONSTITUTION]
    assert not result.widened
    assert {c.chunk.act_slug for c in result.candidates} <= {TENANCY, CONSTITUTION}


def test_too_few_filtered_hits_widens_to_the_full_corpus(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts, min_filtered_hits=20).retrieve("my landlord wants to evict me")
    assert result.widened
    assert EMPLOYMENT in {c.chunk.act_slug for c in result.candidates}


def test_no_route_searches_everything(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts).retrieve("annual records")
    assert result.acts is None
    assert not result.widened


def test_explicit_reference_is_injected_at_sparse_rank_1(parts: tuple[DenseIndex, SparseIndex]) -> None:
    retriever = _retriever(parts)
    result = retriever.retrieve_sparse_only("what does section 9 of the Sample Employment Act say")
    assert result.candidates[0].chunk.chunk_id == f"{EMPLOYMENT}-9"
    hybrid = retriever.retrieve("what does section 9 of the Sample Employment Act say")
    target = next(c for c in hybrid.candidates if c.chunk.chunk_id == f"{EMPLOYMENT}-9")
    assert target.sparse_rank == 1


def test_bare_section_resolves_within_routed_acts(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts).retrieve_sparse_only("tenant complaint under section 41")
    assert result.candidates[0].chunk.chunk_id == f"{TENANCY}-41"


@pytest.mark.parametrize("query", ["section 7 of the Sample Employment Act", "section 99 of the Sample Employment Act"])
def test_repealed_or_unknown_references_are_not_injected(parts: tuple[DenseIndex, SparseIndex], query: str) -> None:
    ids = [c.chunk.chunk_id for c in _retriever(parts).retrieve(query).candidates]
    assert f"{EMPLOYMENT}-7" not in ids
    assert f"{EMPLOYMENT}-99" not in ids


def test_article_reference_hits_the_constitution(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts).retrieve("Article 43")
    assert result.acts == [CONSTITUTION]
    assert result.candidates[0].chunk.chunk_id == f"{CONSTITUTION}-43"


def test_debug_fields_and_timings(parts: tuple[DenseIndex, SparseIndex]) -> None:
    result = _retriever(parts).retrieve("employer leave wages")
    assert set(result.timings_ms) == {"route", "embed", "dense", "sparse", "rrf", "total"}
    assert all(v >= 0 for v in result.timings_ms.values())
    dense_ids = {c.chunk.chunk_id for c in result.candidates if c.dense_rank is not None}
    sparse_ids = {c.chunk.chunk_id for c in result.candidates if c.sparse_rank is not None}
    assert set(result.dense_only_ids) >= dense_ids - sparse_ids
    assert set(result.sparse_only_ids) >= sparse_ids - dense_ids
    assert not set(result.dense_only_ids) & set(result.sparse_only_ids)


def test_single_leg_results_use_their_own_ranks(parts: tuple[DenseIndex, SparseIndex]) -> None:
    retriever = _retriever(parts)
    dense = retriever.retrieve_dense_only("employer leave")
    sparse = retriever.retrieve_sparse_only("employer leave")
    assert [c.dense_rank for c in dense.candidates] == list(range(1, len(dense.candidates) + 1))
    assert all(c.sparse_rank is None for c in dense.candidates)
    assert [c.sparse_rank for c in sparse.candidates] == list(range(1, len(sparse.candidates) + 1))
    assert set(dense.timings_ms) == {"route", "embed", "dense", "rrf", "total"}


@pytest.fixture
def built(tmp_path: Path) -> Settings:
    settings = Settings(chunks_path=tmp_path / "chunks.json", index_dir=tmp_path / "indexes")
    STORE.save(settings.chunks_path)
    build_indexes(settings, EMB)
    return settings


def test_load_retriever_and_cli(built: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    retriever = load_retriever(built, EMB)
    assert retriever.retrieve("landlord").candidates
    assert main(["section 3 eviction notice"], settings=built, embedder=EMB) == 0
    out = capsys.readouterr().out
    assert "dense=" in out and "sparse=" in out and "rrf=" in out


def test_cli_without_indexes_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(chunks_path=tmp_path / "chunks.json", index_dir=tmp_path / "indexes")
    STORE.save(settings.chunks_path)
    assert main(["anything"], settings=settings, embedder=EMB) == 2
    assert "build_index" in capsys.readouterr().err


SMOKE_QUERIES = [
    "my employer fired me without notice",
    "my landlord wants to evict me from my house",
    "I was arrested and held for three days without being taken to court",
    "the shop refused to refund me for a faulty phone",
    "what does section 41 of the Employment Act say",
]


@pytest.mark.real
def test_smoke_queries_against_the_real_indexes(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings()
    if not (settings.dense_index_dir / "meta.json").exists():
        pytest.skip("real indexes not built; run python -m backend.app.ingestion.build_index")
    retriever = load_retriever(settings)
    with capsys.disabled():
        for query in SMOKE_QUERIES:
            result = retriever.retrieve(query)
            print(f"\n{query} -> {result.acts} widened={result.widened}")
            for c in result.candidates[:5]:
                print(f"  {c.rrf_score:.4f} d={c.dense_rank} s={c.sparse_rank} {c.chunk.chunk_id}")
            assert len(result.candidates) == settings.top_n
