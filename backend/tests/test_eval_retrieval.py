import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.evaluation.retrieval_eval import (
    SYSTEMS,
    Cutoffs,
    compare,
    main,
    render_markdown,
    run_retrieval_eval,
    score_ranking,
    summarize,
)
from backend.app.evaluation.schema import GroundTruthEntry, RelevantRef, ResolvedEntry
from backend.app.models import RetrievedChunk, UserLanguage
from backend.app.retrieval.hybrid import RetrievalResult
from backend.tests.fake_pipeline import ACTS, STORE, build_parts, fake_retriever
from backend.tests.fakes import FakeReranker

CUT = Cutoffs(5, 20)
P5, R20, MRR = CUT.names


def _result(ids: list[str]) -> RetrievalResult:
    chunks = [RetrievedChunk(chunk=c, rrf_score=1.0 / (i + 1)) for i, c in enumerate(STORE.get(ids))]
    return RetrievalResult(chunks, None, False, {}, [], [])


class StubRetriever:
    """Fixed ranked lists per mode (same for every question)."""

    def __init__(self, dense: list[str], sparse: list[str], hybrid: list[str]) -> None:
        self.lists = {"dense": dense, "sparse": sparse, "hybrid": hybrid}

    def retrieve(self, question: str) -> RetrievalResult:
        return _result(self.lists["hybrid"])

    def retrieve_dense_only(self, question: str) -> RetrievalResult:
        return _result(self.lists["dense"])

    def retrieve_sparse_only(self, question: str) -> RetrievalResult:
        return _result(self.lists["sparse"])


class ScriptedReranker:
    """Scores docs by a fixed preference for chunk titles (higher = earlier)."""

    def __init__(self, order: list[str]) -> None:
        self.order = order

    def score(self, query: str, docs: list[str]) -> list[float]:
        return [float(-next((i for i, t in enumerate(self.order) if t in d), 99)) for d in docs]


def _resolved(eid: str, relevant: set[str], category: str = "employment", lang: UserLanguage = "en") -> ResolvedEntry:
    entry = GroundTruthEntry(
        id=eid, question=f"question {eid}", lang=lang, category=category, relevant=[RelevantRef(act="x", section="1")]
    )
    return ResolvedEntry(entry, frozenset(relevant))


E = "sample-employment-act-"


def test_score_ranking_hand_computed() -> None:
    ranked = [f"{E}1", f"{E}4", f"{E}2", f"{E}3", f"{E}5", f"{E}6"]
    scores = score_ranking(ranked, frozenset({f"{E}4", f"{E}6"}), CUT)
    assert scores == {P5: pytest.approx(1 / 5), R20: 1.0, MRR: pytest.approx(1 / 2)}


def test_run_with_stub_lists_gives_exact_metrics_per_system_and_category() -> None:
    retriever = StubRetriever(
        dense=[f"{E}1", f"{E}2", f"{E}3"],
        sparse=[f"{E}4", f"{E}1"],
        hybrid=[f"{E}1", f"{E}4", f"{E}2", f"{E}3"],
    )
    reranker = ScriptedReranker(["Unfair termination", "Notice"])  # puts s.4 first, then s.3
    entries = [_resolved("R1", {f"{E}4"}), _resolved("R2", {f"{E}3"}, category="tenancy", lang="sw")]
    translated: list[tuple[str, str]] = []

    def to_english(question: str, lang: UserLanguage) -> str:
        translated.append((question, lang))
        return question

    result = run_retrieval_eval(entries, retriever, reranker, to_english, Settings(acts=ACTS), "hash")
    assert translated == [("question R1", "en"), ("question R2", "sw")]
    rows = {r["id"]: r["systems"] for r in result["per_query"]}
    assert rows["R1"]["faiss"][MRR] == 0.0
    assert rows["R1"]["bm25"][MRR] == 1.0
    assert rows["R1"]["hybrid"][MRR] == pytest.approx(1 / 2)
    assert rows["R1"]["hybrid_rerank"]["ranked"] == [f"{E}4", f"{E}3", f"{E}1", f"{E}2"]
    assert rows["R2"]["hybrid_rerank"][MRR] == pytest.approx(1 / 2)
    assert rows["R2"]["faiss"][P5] == pytest.approx(1 / 5)
    summary = result["summary"]
    assert summary["bm25"]["mean"][MRR] == pytest.approx(0.5)  # 1.0 and 0.0
    assert summary["hybrid_rerank"]["mean"][MRR] == pytest.approx(0.75)
    assert summary["faiss"]["by_category"]["tenancy"] == {"n": 1, P5: pytest.approx(0.2), R20: 1.0, MRR: 1 / 3}
    assert result["config"]["corpus_hash"] == "hash"
    comparison = {(c["system"], c["metric"]): c for c in result["comparisons"]}
    assert comparison[("hybrid_rerank", MRR)]["baseline"] == "bm25"
    assert comparison[("hybrid_rerank", MRR)]["diff"] == pytest.approx(0.25)


def test_compare_picks_best_baseline_per_metric() -> None:
    rows = [
        {"id": "a", "category": "c", "systems": {s: {P5: v, R20: 1.0, MRR: m} for s, v, m in spec}}
        for spec in (
            [("faiss", 0.4, 0.2), ("bm25", 0.2, 1.0), ("hybrid", 0.6, 1.0), ("hybrid_rerank", 0.6, 1.0)],
            [("faiss", 0.4, 0.2), ("bm25", 0.2, 0.5), ("hybrid", 0.4, 0.5), ("hybrid_rerank", 0.4, 1.0)],
        )
    ]
    summary = summarize(rows, CUT)
    out = {(c["system"], c["metric"]): c for c in compare(rows, summary, CUT, resamples=200, seed=0)}
    assert out[("hybrid", P5)]["baseline"] == "faiss"
    assert out[("hybrid", P5)]["diff"] == pytest.approx(0.1)
    assert out[("hybrid", MRR)]["baseline"] == "bm25"
    assert out[("hybrid", R20)]["baseline"] == "faiss"  # tie -> first listed
    assert "CI" in render_markdown(
        {"n_queries": 2, "metrics": list(CUT.names), "summary": summary, "comparisons": list(out.values())}
    )


def _write_truth(settings: Settings, entries: list[dict[str, object]]) -> None:
    settings.ground_truth_path.parent.mkdir(parents=True, exist_ok=True)
    settings.ground_truth_path.write_text(json.dumps(entries), encoding="utf-8")


def test_cli_runs_on_the_fake_stack_and_saves_json_and_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    STORE.save(tmp_path / "chunks.json")
    settings = Settings(
        chunks_path=tmp_path / "chunks.json", acts=ACTS, eval_dir=tmp_path / "eval", eval_bootstrap_resamples=100
    )
    _write_truth(
        settings,
        [
            {
                "id": "R01",
                "question": "employer fired me unfair termination",
                "lang": "en",
                "category": "employment",
                "relevant": [{"act": "Sample Employment Act", "section": "4"}],
            },
            {
                "id": "R02",
                "question": "landlord wants to evict tenant",
                "lang": "en",
                "category": "tenancy",
                "relevant": [{"act": "Sample Tenancy Act", "section": "3"}],
            },
        ],
    )
    retriever = fake_retriever(build_parts(tmp_path / "sparse"), settings)
    code = main([], settings, retriever, FakeReranker(), lambda q, lang: q)
    assert code == 0
    saved = json.loads((settings.eval_results_dir / "retrieval.json").read_text(encoding="utf-8"))
    assert saved["n_queries"] == 2
    assert set(saved["summary"]) == set(SYSTEMS)
    assert all(row["systems"]["hybrid"][MRR] > 0 for row in saved["per_query"])
    assert (settings.eval_results_dir / "retrieval.md").read_text(encoding="utf-8").startswith("Queries: 2")
    assert "| hybrid_rerank |" in capsys.readouterr().out


def test_cli_rejects_invalid_truth_and_missing_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    STORE.save(tmp_path / "chunks.json")
    settings = Settings(chunks_path=tmp_path / "chunks.json", acts=ACTS, eval_dir=tmp_path / "eval")
    retriever = StubRetriever([], [], [])
    assert main([], settings, retriever, FakeReranker(), lambda q, lang: q) == 1
    assert "does not exist" in capsys.readouterr().err
    missing = settings.model_copy(update={"chunks_path": tmp_path / "none.json"})
    assert main([], missing, retriever, FakeReranker(), lambda q, lang: q) == 2
