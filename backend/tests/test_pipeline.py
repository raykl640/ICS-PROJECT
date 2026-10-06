from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.ingestion.build_index import build_indexes
from backend.app.models import RetrievedChunk
from backend.app.retrieval import hybrid
from backend.app.retrieval import pipeline as pipeline_module
from backend.app.retrieval.hybrid import RetrievalResult
from backend.app.retrieval.meta import IndexMismatchError
from backend.app.retrieval.pipeline import ContextPipeline, load_pipeline
from backend.tests.corpus import EMPLOYMENT, make_chunk
from backend.tests.fake_pipeline import EMB, STORE, fake_pipeline
from backend.tests.fakes import FakeReranker
from backend.tests.test_reranker import ScriptedReranker

STAGES = {"route", "embed", "dense", "sparse", "rrf", "rerank", "scope", "total"}
GARBAGE = "qxzv blorp zzkt wqmmf"
# FakeReranker scores = shared query words, so 1.0 means "at least one shared word".
FAKE_THRESHOLD = 1.0


class StubRetriever:
    """Returns a fixed candidate list for any question."""

    def __init__(self, candidates: list[RetrievedChunk]) -> None:
        self.candidates = candidates

    def retrieve(self, question: str) -> RetrievalResult:
        timings = {"route": 0.0, "embed": 0.0, "dense": 0.0, "sparse": 0.0, "rrf": 0.0, "total": 0.0}
        return RetrievalResult(self.candidates, None, False, timings, [], [])


class StubScope:
    """Returns a fixed scope margin for any question."""

    def __init__(self, margin: float) -> None:
        self.value = margin

    def margin(self, question: str) -> float:
        return self.value


OUT_OF_SCOPE = -1.0
IN_SCOPE = 1.0


class SpyLLM:
    """Records any use; the null path must leave it untouched."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.health_checks = 0

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        self.prompts.append(prompt)
        yield ""

    async def health(self) -> bool:
        self.health_checks += 1
        return True


def _candidates(n: int) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(chunk=make_chunk(EMPLOYMENT, str(i), f"T{i}", f"Text {i}."), rrf_score=1 / (60 + i))
        for i in range(1, n + 1)
    ]


def _stub(n: int, scores: list[float], threshold: float = 0.0, margin: float = OUT_OF_SCOPE) -> ContextPipeline:
    return ContextPipeline(
        StubRetriever(_candidates(n)),
        ScriptedReranker(scores),
        StubScope(margin),
        Settings(relevance_threshold=threshold, scope_margin=0.0),
    )


@pytest.fixture(scope="module")
def pipe(tmp_path_factory: pytest.TempPathFactory) -> ContextPipeline:
    return fake_pipeline(tmp_path_factory.mktemp("sp"), Settings(top_n=10, relevance_threshold=FAKE_THRESHOLD))


def test_on_topic_question_returns_top_5_sorted(pipe: ContextPipeline) -> None:
    result = pipe.retrieve_context("my employer fired me and did not pay wages or leave")
    assert not result.null
    assert len(result.chunks) == 5
    scores = [c.rerank_score for c in result.chunks]
    assert all(s is not None for s in scores)
    assert scores == sorted(scores, reverse=True)  # type: ignore[type-var]
    assert result.debug.scores == [(c.chunk.chunk_id, c.rerank_score) for c in result.chunks]
    assert result.debug.candidates == 10
    assert set(result.debug.timings_ms) == STAGES
    assert all(ms >= 0 for ms in result.debug.timings_ms.values())


def test_garbage_input_is_null_but_keeps_debug_scores(pipe: ContextPipeline) -> None:
    result = pipe.retrieve_context(GARBAGE)
    assert result.null
    assert result.chunks == []
    assert len(result.debug.scores) == 5
    assert all(score < FAKE_THRESHOLD for _, score in result.debug.scores)


def test_null_path_never_touches_the_llm(pipe: ContextPipeline) -> None:
    spy = SpyLLM()
    result = pipe.retrieve_context(GARBAGE)
    assert result.null and result.chunks == []
    assert spy.prompts == [] and spy.health_checks == 0
    assert not any("LLM" in name or "llm" in name for name in vars(pipeline_module))


def test_empty_candidate_list_is_null() -> None:
    result = _stub(0, []).retrieve_context("q")
    assert result.null and result.chunks == [] and result.debug.scores == []


@pytest.mark.parametrize(
    ("scores", "null"),
    [
        ([-1.0, -2.0, -3.0, -4.0, -5.0], True),
        ([2.0, -2.0, -3.0, -4.0, -5.0], True),
        ([2.0, 1.0, -3.0, -4.0, -5.0], False),
        ([0.0, 0.0, -3.0, -4.0, -5.0], False),  # inclusive boundary
    ],
)
def test_null_iff_fewer_than_two_at_or_above_threshold(scores: list[float], null: bool) -> None:
    result = _stub(5, scores).retrieve_context("q")
    assert result.null is null
    assert len(result.chunks) == (0 if null else 5)


def test_confident_result_keeps_all_top_chunks_even_below_threshold() -> None:
    result = _stub(8, [3.0, 2.0, -1.0, -2.0, -3.0, -4.0, -5.0, -6.0]).retrieve_context("q")
    assert [c.rerank_score for c in result.chunks] == [3.0, 2.0, -1.0, -2.0, -3.0]


def test_fewer_than_five_candidates() -> None:
    result = _stub(2, [1.0, 0.5]).retrieve_context("q")
    assert not result.null and len(result.chunks) == 2
    assert _stub(1, [9.0]).retrieve_context("q").null


def test_identical_scores_keep_rrf_order() -> None:
    result = _stub(7, [1.0] * 7).retrieve_context("q")
    assert [c.chunk.section_num for c in result.chunks] == ["1", "2", "3", "4", "5"]


def test_threshold_comes_from_settings() -> None:
    assert _stub(3, [1.0, 1.0, 1.0], threshold=1.5).retrieve_context("q").null


def test_in_scope_question_is_answered_even_when_the_reranker_is_not_confident() -> None:
    result = _stub(5, [-10.0] * 5, margin=IN_SCOPE).retrieve_context("q")
    assert not result.null and len(result.chunks) == 5
    assert result.debug.scope_margin == IN_SCOPE


def test_scope_margin_boundary_is_inclusive() -> None:
    assert not _stub(5, [-10.0] * 5, margin=0.0).retrieve_context("q").null


def test_out_of_scope_and_not_confident_is_null() -> None:
    result = _stub(5, [-10.0] * 5, margin=OUT_OF_SCOPE).retrieve_context("q")
    assert result.null and result.chunks == []
    assert result.debug.scope_margin == OUT_OF_SCOPE


def test_out_of_scope_but_confident_is_answered() -> None:
    assert not _stub(5, [3.0, 2.0, -1.0, -2.0, -3.0], margin=OUT_OF_SCOPE).retrieve_context("q").null


def test_in_scope_still_needs_min_confident_chunks_candidates() -> None:
    assert _stub(1, [-10.0], margin=IN_SCOPE).retrieve_context("q").null
    assert _stub(0, [], margin=IN_SCOPE).retrieve_context("q").null


def test_fake_pipeline_answers_in_scope_wording_with_no_reranker_overlap(pipe: ContextPipeline) -> None:
    result = pipe.retrieve_context("my boss sacked me")
    assert sum(score >= FAKE_THRESHOLD for _, score in result.debug.scores) < 2  # the reranker alone would say null
    assert result.debug.scope_margin >= Settings().scope_margin
    assert not result.null


def test_load_pipeline_from_built_indexes(tmp_path: Path) -> None:
    settings = Settings(chunks_path=tmp_path / "chunks.json", index_dir=tmp_path / "indexes")
    STORE.save(settings.chunks_path)
    build_indexes(settings, EMB)
    pipe = load_pipeline(settings, EMB, FakeReranker())
    assert pipe.retrieve_context("landlord evict tenant").chunks


def test_missing_indexes_fail_before_any_model_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CI has no model cache: the index check must come first, or a download is attempted (and blocked)."""

    def no_model(*args: object) -> None:
        raise AssertionError("a model was loaded before the indexes were checked")

    monkeypatch.setattr(hybrid, "STEmbedder", no_model)
    monkeypatch.setattr(pipeline_module, "CEReranker", no_model)
    settings = Settings(chunks_path=tmp_path / "chunks.json", index_dir=tmp_path / "indexes")
    STORE.save(settings.chunks_path)
    with pytest.raises(IndexMismatchError):
        load_pipeline(settings)
