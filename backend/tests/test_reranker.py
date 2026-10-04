from collections.abc import Iterator, Sequence
from typing import Any

import pytest

from backend.app.models import RetrievedChunk
from backend.app.retrieval import reranker
from backend.app.retrieval.reranker import CEReranker, is_confident, pair_text, rerank
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, make_chunk
from backend.tests.fakes import FakeReranker


class ScriptedReranker:
    """Returns the given scores in candidate order and records each call."""

    def __init__(self, scores: Sequence[float]) -> None:
        self.scores = list(scores)
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, docs: list[str]) -> list[float]:
        self.calls.append((query, docs))
        return self.scores[: len(docs)]


def _candidates(n: int) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk=make_chunk(EMPLOYMENT, str(i), f"Title {i}", f"Body text {i}."), dense_rank=i, rrf_score=1 / (60 + i)
        )
        for i in range(1, n + 1)
    ]


def _scored(*scores: float | None) -> list[RetrievedChunk]:
    return [c.model_copy(update={"rerank_score": s}) for c, s in zip(_candidates(len(scores)), scores, strict=True)]


def test_pair_text_names_act_unit_number_and_title() -> None:
    section = make_chunk(EMPLOYMENT, "41", "Notice", "Give notice.")
    article = make_chunk(CONSTITUTION, "27", "Equality", "All equal.", unit_type="article")
    schedule = make_chunk(CONSTITUTION, "First Schedule", "Counties", "A list.", unit_type="schedule")
    assert pair_text(section) == "Sample Employment Act Section 41 Notice: Give notice."
    assert pair_text(article) == "Sample Constitution Article 27 Equality: All equal."
    assert pair_text(schedule) == "Sample Constitution First Schedule Counties: A list."


def test_rerank_sorts_by_score_and_keeps_retrieval_fields() -> None:
    model = ScriptedReranker([0.5, 3.0, -2.0, 1.0])
    out = rerank(model, "q", _candidates(4), top=5)
    assert [c.chunk.section_num for c in out] == ["2", "4", "1", "3"]
    assert [c.rerank_score for c in out] == [3.0, 1.0, 0.5, -2.0]
    assert [c.dense_rank for c in out] == [2, 4, 1, 3]
    assert model.calls[0][1][0] == "Sample Employment Act Section 1 Title 1: Body text 1."


def test_rerank_returns_exactly_top() -> None:
    out = rerank(ScriptedReranker([float(i) for i in range(20)]), "q", _candidates(20), top=5)
    assert len(out) == 5
    assert [c.rerank_score for c in out] == [19.0, 18.0, 17.0, 16.0, 15.0]


def test_rerank_short_list_returns_all() -> None:
    assert len(rerank(ScriptedReranker([1.0, 2.0, 3.0]), "q", _candidates(3), top=5)) == 3


def test_rerank_empty_list_never_calls_the_model() -> None:
    model = ScriptedReranker([])
    assert rerank(model, "q", [], top=5) == []
    assert model.calls == []


def test_ties_keep_the_rrf_order() -> None:
    out = rerank(ScriptedReranker([1.0, 2.0, 1.0, 2.0, 1.0, 1.0]), "q", _candidates(6), top=5)
    assert [c.chunk.section_num for c in out] == ["2", "4", "1", "3", "5"]


def test_rerank_with_fake_handles_an_extremely_long_chunk() -> None:
    long = RetrievedChunk(chunk=make_chunk(EMPLOYMENT, "9", "Long", "word " * 50_000 + "notice"), rrf_score=0.1)
    out = rerank(FakeReranker(), "notice", [long, *_candidates(2)], top=5)
    assert out[0].chunk.section_num == "9"


@pytest.mark.parametrize(
    ("scores", "confident"),
    [
        ((), False),
        ((-1.0, -2.0, -3.0), False),
        ((4.0, -1.0, -2.0), False),
        ((4.0, 0.5, -2.0), True),
        ((0.0, 0.0), True),  # boundary is inclusive
        ((0.0, -0.001), False),
        ((3.0, None), False),
    ],
)
def test_is_confident_needs_min_chunks_at_or_above_threshold(scores: tuple[float, ...], confident: bool) -> None:
    assert is_confident(_scored(*scores), threshold=0.0, min_chunks=2) is confident


class _FakeCrossEncoderModel:
    """Stands in for sentence_transformers.CrossEncoder: one score per pair, records predict calls."""

    def __init__(self) -> None:
        self.predict_calls: list[dict[str, Any]] = []

    def predict(self, pairs: list[tuple[str, str]], **kwargs: Any) -> list[float]:
        self.predict_calls.append({"pairs": pairs, **kwargs})
        return [float(len(doc)) for _, doc in pairs]


@pytest.fixture
def fake_loader(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[str, int]]]:
    loads: list[tuple[str, int]] = []
    model = _FakeCrossEncoderModel()

    def load(name: str, max_length: int) -> _FakeCrossEncoderModel:
        loads.append((name, max_length))
        return model

    monkeypatch.setattr(reranker, "_build_cross_encoder", load)
    monkeypatch.setattr(reranker, "_MODELS", {})
    yield loads


def test_ce_reranker_loads_lazily_once_per_process(fake_loader: list[tuple[str, int]]) -> None:
    first = CEReranker("m", max_length=512, batch_size=8)
    second = CEReranker("m", max_length=512, batch_size=8)
    assert fake_loader == []
    assert first.score("q", []) == []
    assert fake_loader == []
    assert first.score("q", ["ab", "abcd"]) == [2.0, 4.0]
    assert second.score("q", ["a"]) == [1.0]
    assert fake_loader == [("m", 512)]


def test_ce_reranker_warmup_loads_and_scores_once(fake_loader: list[tuple[str, int]]) -> None:
    ce = CEReranker("m", max_length=512, batch_size=8)
    ce.warmup()
    model = reranker._MODELS[("m", 512)]
    assert isinstance(model, _FakeCrossEncoderModel)
    assert len(model.predict_calls) == 1
    assert model.predict_calls[0]["batch_size"] == 8


@pytest.mark.real
def test_real_cross_encoder_prefers_on_topic_chunks() -> None:
    ce = CEReranker("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512, batch_size=8)
    # Handwritten paraphrases, not statute text.
    pairs = [
        (
            "my employer fired me without any notice",
            "Employment Act Section 1 Termination: an employer must give written notice before ending a contract.",
            "Traffic Act Section 1 Licences: every driver must carry a valid driving licence on the road.",
        ),
        (
            "can my landlord throw me out of my house",
            "Rent Act Section 1 Eviction: a landlord may not evict a tenant without a court order.",
            "Consumer Act Section 1 Warranties: goods sold must be fit for the purpose described.",
        ),
        (
            "how long can police hold me after arrest",
            "Procedure Act Section 1 Arrest: an arrested person must be brought before a court within 24 hours.",
            "Land Act Section 1 Registration: every land transaction shall be entered in the register.",
        ),
    ]
    for query, on_topic, off_topic in pairs:
        on, off = ce.score(query, [on_topic, off_topic])
        assert on > off, query
    long_doc = "Employment Act Section 2 Records: " + "the employer keeps records. " * 2000
    assert len(ce.score("records", [long_doc])) == 1  # tokenizer truncation, no crash


def test_rerank_rejects_a_score_count_mismatch() -> None:
    with pytest.raises(ValueError, match="2 scores for 3 candidates"):
        rerank(ScriptedReranker([1.0, 2.0]), "q", _candidates(3), top=5)
