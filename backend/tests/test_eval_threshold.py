import json
from pathlib import Path

import pytest

from backend.app.config import ROOT_DIR, Settings
from backend.app.evaluation.threshold import (
    OUT_OF_CORPUS,
    candidates,
    evaluate,
    kth_score,
    main,
    recommend,
    sweep,
)
from backend.tests.fake_pipeline import ACTS, STORE, fake_pipeline

IN = [2.0, 1.0, -1.0, None]
OUT = [-6.0, -3.0, 1.5]


def test_kth_score() -> None:
    assert kth_score([0.5, 3.0, 1.0], 2) == 1.0
    assert kth_score([0.5], 2) is None


def test_evaluate_counts_null_as_positive_and_is_inclusive() -> None:
    point = evaluate(0.0, IN, OUT)
    assert (point.tp, point.fp, point.fn, point.tn) == (2, 2, 1, 2)
    assert point.precision == pytest.approx(0.5)
    assert point.recall == pytest.approx(2 / 3)
    assert point.f1 == pytest.approx(4 / 7)
    assert evaluate(1.0, [1.0], []).fp == 0  # score == threshold is confident (D13)
    empty = evaluate(10.0, [], [])
    assert (empty.precision, empty.recall, empty.f1) == (0.0, 0.0, 0.0)


def test_candidates_are_midpoints_plus_outer_bounds() -> None:
    assert candidates([*IN, *OUT]) == [-6.5, -4.5, -2.0, 0.0, 1.25, 1.75, 2.5]
    assert candidates([None]) == [0.0]


def test_sweep_and_recommendation_prefer_fewer_refused_in_corpus_on_f1_ties() -> None:
    points = {p.threshold: p for p in sweep(IN, OUT)}
    assert points[-2.0].f1 == pytest.approx(2 / 3)
    assert points[1.75].f1 == pytest.approx(2 / 3)
    best = recommend(list(points.values()))
    assert best.threshold == -2.0
    assert (best.tp, best.fp, best.fn, best.tn) == (2, 1, 1, 3)


def test_shipped_out_of_corpus_questions_are_valid_and_unique() -> None:
    queries = OUT_OF_CORPUS.validate_json((ROOT_DIR / "eval" / "out_of_corpus.json").read_bytes())
    assert len(queries) == 15
    assert len({q.id for q in queries}) == len({q.question for q in queries}) == 15


def test_cli_on_the_fake_stack_prints_recommendation_without_touching_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    STORE.save(tmp_path / "chunks.json")
    settings = Settings(chunks_path=tmp_path / "chunks.json", acts=ACTS, eval_dir=tmp_path / "eval")
    settings.eval_dir.mkdir()
    truth = [
        {
            "id": "R01",
            "question": "employer must prove a valid reason for unfair termination of employment",
            "lang": "en",
            "category": "employment",
            "relevant": [{"act": "Sample Employment Act", "section": "4"}],
        }
    ]
    settings.ground_truth_path.write_text(json.dumps(truth), encoding="utf-8")
    settings.out_of_corpus_path.write_text(json.dumps([{"id": "O01", "question": "qxzv blorp"}]), encoding="utf-8")
    pipeline = fake_pipeline(tmp_path / "sparse", settings)
    assert main([], settings, pipeline.retrieve_context, lambda q, lang: q) == 0
    out = capsys.readouterr().out
    assert "recommended relevance_threshold = " in out
    saved = json.loads((settings.eval_results_dir / "threshold.json").read_text(encoding="utf-8"))
    assert saved["n_in"] == 1
    assert saved["n_out"] == 1
    assert saved["recommended"]["f1"] == 1.0
    assert saved["out_of_corpus"][0]["kth_score"] == 0.0  # no word overlap with the fake reranker
    assert settings.relevance_threshold == 0.0


def test_cli_exit_codes_for_bad_inputs(tmp_path: Path) -> None:
    STORE.save(tmp_path / "chunks.json")
    settings = Settings(chunks_path=tmp_path / "chunks.json", acts=ACTS, eval_dir=tmp_path / "eval")
    pipeline = fake_pipeline(tmp_path / "sparse", settings)
    assert main([], settings, pipeline.retrieve_context, lambda q, lang: q) == 1
    missing = settings.model_copy(update={"chunks_path": tmp_path / "none.json"})
    assert main([], missing, pipeline.retrieve_context, lambda q, lang: q) == 2
