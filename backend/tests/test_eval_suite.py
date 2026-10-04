import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.evaluation.functional import FunctionalRecord
from backend.app.evaluation.suite import main
from backend.tests.fake_pipeline import ACTS, STORE


def test_only_the_report_runs_without_inputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(eval_dir=tmp_path)
    assert main([], settings) == 0
    out = capsys.readouterr().out
    assert "not written yet (human task)" in out
    assert "steps run: report; failed: none" in out
    assert settings.eval_report_path.exists()


def test_steps_with_inputs_run_and_failures_are_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    STORE.save(tmp_path / "chunks.json")
    settings = Settings(chunks_path=tmp_path / "chunks.json", acts=ACTS, eval_dir=tmp_path / "eval")
    settings.eval_results_dir.mkdir(parents=True)
    settings.ground_truth_path.write_text("[]", encoding="utf-8")
    record = FunctionalRecord(id="F01", question="q", lang="en", category="c", null_response=True, disclaimer="d")
    (settings.eval_results_dir / "functional.json").write_text(json.dumps([record.model_dump()]), encoding="utf-8")
    settings.usability_responses_path.write_text("participant,clarity\nP1,9\n", encoding="utf-8")
    assert main([], settings) == 1
    assert "steps run: validate, grounding, usability, report; failed: validate, usability" in capsys.readouterr().out
