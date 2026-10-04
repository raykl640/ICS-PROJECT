import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.config import Settings
from backend.app.evaluation.functional import FunctionalRecord
from backend.app.evaluation.grounding import check_record, grounding_report, main, render
from backend.app.models import CitationCheck

GOOD_ANSWER = (
    "## RIGHTS EXPLANATION\nUnder the Employment Act, Section 41, you must be heard first.\n\n"
    "## RECOMMENDED STEPS\n1. Write to your employer.\n\n"
    "## FORMAL LETTER\nDear [Employer Name],\nI write about my dismissal on [date].\nYours faithfully,\n[Your Name]\n"
)


def _record(**overrides: Any) -> FunctionalRecord:
    base: dict[str, Any] = {
        "id": "F01",
        "question": "q",
        "lang": "en",
        "category": "employment",
        "answer_en": GOOD_ANSWER,
        "citation_check": CitationCheck(verified=["Employment Act s. 41"]),
        "format_ok": True,
        "disclaimer": "legal information, not legal advice",
    }
    return FunctionalRecord(**(base | overrides))


def test_good_response_passes_every_check() -> None:
    assert all(check_record(_record()).values())


def test_bad_response_fails_the_right_checks() -> None:
    bad = _record(
        answer_en="## RIGHTS EXPLANATION\nYou have rights.\n## FORMAL LETTER\nDear Sir, please pay me.",
        citation_check=CitationCheck(verified=["Employment Act s. 41"], unmatched=["Employment Act s. 99"]),
        disclaimer="",
    )
    checks = check_record(bad)
    assert checks == {
        "null_path_correct": True,
        "disclaimer_present": False,
        "has_citation": True,
        "citations_verified": False,
        "sections_present": False,
        "letter_placeholders": False,
    }
    uncited = check_record(_record(citation_check=CitationCheck()))
    assert uncited["has_citation"] is False
    assert uncited["citations_verified"] is False


def test_null_paths_and_errors() -> None:
    correct_null = check_record(_record(null_response=True, expect_null=True, answer_en=""))
    assert correct_null["null_path_correct"] is True
    assert correct_null["disclaimer_present"] is True
    assert correct_null["has_citation"] is None
    wrong_null = check_record(_record(null_response=True, expect_null=False, answer_en=""))
    assert wrong_null["null_path_correct"] is False
    answered_out_of_corpus = check_record(_record(expect_null=True))
    assert answered_out_of_corpus["null_path_correct"] is False
    errored = check_record(_record(error="HTTP 503 busy"))
    assert errored["null_path_correct"] is False
    assert [k for k, v in errored.items() if v is not None] == ["null_path_correct"]


def test_report_summary_and_markdown() -> None:
    records = [_record(), _record(id="F02", disclaimer=""), _record(id="F03", null_response=True, expect_null=True)]
    report = grounding_report(records)
    summary = report["summary"]
    assert summary["disclaimer_present"] == {"passed": 2, "applicable": 3, "rate": pytest.approx(2 / 3)}
    assert summary["has_citation"]["applicable"] == 2
    text = render(report)
    assert "| disclaimer_present | 2 | 3 | 67% |" in text
    assert "- disclaimer_present failed: F02" in text


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(eval_dir=tmp_path)
    assert main([], settings) == 1
    settings.eval_results_dir.mkdir()
    (settings.eval_results_dir / "functional.json").write_text(json.dumps([_record().model_dump()]), encoding="utf-8")
    assert main([], settings) == 0
    assert json.loads((settings.eval_results_dir / "grounding.json").read_text(encoding="utf-8"))["n_responses"] == 1
    assert "| sections_present | 1 | 1 | 100% |" in capsys.readouterr().out
