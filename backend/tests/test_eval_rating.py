import csv
import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.evaluation.functional import FunctionalRecord, SourceRecord
from backend.app.evaluation.rating import (
    COLUMNS,
    agreement_main,
    agreement_report,
    make_sheets_main,
    read_sheets,
    render,
    write_sheets,
)
from backend.app.models import CitationCheck

SOURCE = SourceRecord(
    chunk_id="sample-employment-act-4",
    act="Sample Employment Act",
    unit_type="section",
    section_num="4",
    section_title="Unfair termination",
    page=1,
    rank=1,
    truncated=False,
    text="Invented source text.",
)


def _records() -> list[FunctionalRecord]:
    base = {"question": "q?", "lang": "en", "category": "employment", "answer_en": "## RIGHTS EXPLANATION\nx"}
    return [
        FunctionalRecord(
            id="F01", **base, sources=[SOURCE], citation_check=CitationCheck(verified=["Sample Employment Act s. 4"])
        ),
        FunctionalRecord(id="F02", **base, null_response=True),
        FunctionalRecord(id="F03", **base, error="HTTP 503 busy"),
        FunctionalRecord(id="F04", **(base | {"lang": "sw"}), sections_user={"rights": "[sw] haki", "steps": ""}),
    ]


def _fill(path: Path, ratings: dict[str, tuple[str, str]]) -> None:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        row["grounding"], row["citations_correct"] = ratings.get(row["response_id"], ("", ""))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_sheets_cover_answered_questions_only_and_responses_md_has_sources(tmp_path: Path) -> None:
    paths = write_sheets(_records(), tmp_path, 3)
    assert [p.name for p in paths] == ["rater_1.csv", "rater_2.csv", "rater_3.csv"]
    with paths[0].open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["response_id"] for r in rows] == ["F01", "F04"]
    assert all(r["grounding"] == "" for r in rows)
    md = (tmp_path / "responses.md").read_text(encoding="utf-8")
    assert "Invented source text." in md
    assert "sample-employment-act-4 — Sample Employment Act section 4" in md
    assert "[sw] haki" in md
    assert "F02" not in md


def test_agreement_with_known_kappa(tmp_path: Path) -> None:
    paths = write_sheets(_records(), tmp_path, 3)
    # F01 grounding: 2,2,1 ; F04: 0,0,0 -> counts [[0,1,2],[3,0,0]]; P̄ = (1/3 + 1)/2 = 2/3;
    # shares: 0 -> 3/6, 1 -> 1/6, 2 -> 2/6 -> P_e = (9+1+4)/36 = 14/36; kappa = (2/3 - 14/36)/(1 - 14/36) = 10/22.
    _fill(paths[0], {"F01": ("2", "yes"), "F04": ("0", "NA")})
    _fill(paths[1], {"F01": ("2", "yes"), "F04": ("0", "na")})
    _fill(paths[2], {"F01": ("1", "yes"), "F04": ("0", "")})
    report = agreement_report(read_sheets(paths))
    grounding = report["grounding"]
    assert grounding["items"] == 2
    assert grounding["kappa"] == pytest.approx(10 / 22)
    assert grounding["unanimous"] == pytest.approx(0.5)
    assert grounding["distribution"] == {"0": 3, "1": 1, "2": 2}
    assert grounding["mean_score"] == pytest.approx(5 / 6)
    citations = report["citations_correct"]
    assert citations["items"] == 1  # F04 left blank by rater 3
    assert citations["skipped"] == 1
    assert citations["kappa"] is None  # everyone said yes: chance agreement 1
    assert "| grounding | 2 | 50% | 67% | 0.455 |" in render(report)


def test_invalid_values_are_reported(tmp_path: Path) -> None:
    paths = write_sheets(_records(), tmp_path, 2)
    _fill(paths[0], {"F01": ("3", "maybe")})
    problems = read_sheets(paths).problems
    assert problems == [
        "rater_1.csv line 2: grounding='3' not in 0/1/2",
        "rater_1.csv line 2: citations_correct='maybe' not in yes/no/na",
    ]


def test_empty_agreement_renders_na(tmp_path: Path) -> None:
    report = agreement_report(read_sheets(write_sheets(_records(), tmp_path, 2)))
    assert report["grounding"]["kappa"] is None
    assert "| grounding | 0 | n/a | n/a | n/a |" in render(report)


def test_clis(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(eval_dir=tmp_path, eval_raters=2)
    assert make_sheets_main([], settings) == 1  # no functional.json yet
    settings.eval_results_dir.mkdir()
    (settings.eval_results_dir / "functional.json").write_text(
        json.dumps([r.model_dump() for r in _records()]), encoding="utf-8"
    )
    assert agreement_main([], settings) == 1  # no sheets yet
    assert make_sheets_main([], settings) == 0
    assert make_sheets_main([], settings) == 1  # would overwrite ratings
    assert make_sheets_main(["--force"], settings) == 0
    sheets = sorted(settings.ratings_dir.glob("rater_*.csv"))
    _fill(sheets[0], {"F01": ("2", "yes"), "F04": ("1", "no")})
    _fill(sheets[1], {"F01": ("2", "yes"), "F04": ("9", "no")})
    assert agreement_main([], settings) == 1
    _fill(sheets[1], {"F01": ("2", "yes"), "F04": ("1", "no")})
    assert agreement_main([], settings) == 0
    saved = json.loads((settings.eval_results_dir / "agreement.json").read_text(encoding="utf-8"))
    assert saved["grounding"]["unanimous"] == 1.0
    assert "Fleiss' kappa" in capsys.readouterr().out
