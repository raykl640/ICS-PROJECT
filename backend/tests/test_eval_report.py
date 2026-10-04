from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.evaluation import grounding, threshold, usability
from backend.app.evaluation.common import write_json
from backend.app.evaluation.functional import FunctionalRecord
from backend.app.evaluation.report import SECTIONS, build_report, main


def test_empty_results_dir_gives_placeholders_for_every_section(tmp_path: Path) -> None:
    report = build_report(tmp_path)
    assert report.startswith("# HakiAI evaluation report")
    assert report.count("_Not available yet") == len(SECTIONS)
    assert "`python eval/run_retrieval.py`" in report


def test_partial_results_render_and_the_rest_are_skipped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(eval_dir=tmp_path)
    results = settings.eval_results_dir
    record = FunctionalRecord(id="F01", question="q", lang="en", category="c", null_response=True, disclaimer="d")
    write_json(results / "grounding.json", grounding.grounding_report([record]))
    write_json(
        results / "threshold.json",
        threshold.tune([{"id": "R1", "kth_score": 2.0}], [{"id": "O1", "kth_score": -5.0}], settings),
    )
    write_json(results / "usability.json", usability.analyze([], resamples=10, seed=0))
    assert main([], settings) == 0
    report = settings.eval_report_path.read_text(encoding="utf-8")
    assert "| null_path_correct | 0 | 1 | 0% |" in report
    assert "| recommended | -1.5 | 1.00 | 1.00 | 1.00 | 0 | 0 |" in report
    assert "| sus | 0 |" in report
    assert report.count("_Not available yet") == 3
    assert "3 of 6 sections have results" in capsys.readouterr().out
