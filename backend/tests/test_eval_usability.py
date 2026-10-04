import csv
import json
from pathlib import Path

import pytest

from backend.app.config import ROOT_DIR, Settings
from backend.app.evaluation.usability import COLUMNS, analyze, main, parse_responses, render, sus_score


def test_sus_score_known_examples() -> None:
    assert sus_score([3] * 10) == 50.0
    assert sus_score([5, 1] * 5) == 100.0
    assert sus_score([1, 5] * 5) == 0.0
    # Odd items 4,5,4,3,4 -> 3+4+3+2+3 = 15; even items 2,1,2,3,1 -> 3+4+3+2+4 = 16; (15+16) x 2.5 = 77.5
    assert sus_score([4, 2, 5, 1, 4, 2, 3, 3, 4, 1]) == 77.5
    with pytest.raises(ValueError):
        sus_score([3] * 9)
    with pytest.raises(ValueError):
        sus_score([6] + [3] * 9)


def _row(pid: str, before: int, after: int, sus: list[int]) -> dict[str, str]:
    values = [before, after, 4, 5, *sus]
    return {"participant": pid, **{col: str(v) for col, v in zip(COLUMNS[1:], values, strict=True)}}


def test_parse_and_analyze_paired_change() -> None:
    rows = [
        _row("P1", 2, 4, [3] * 10),
        _row("P2", 3, 3, [5, 1] * 5),
        _row("P3", 4, 3, [4, 2, 5, 1, 4, 2, 3, 3, 4, 1]),
    ]
    participants, problems = parse_responses(rows)
    assert problems == []
    result = analyze(participants, resamples=200, seed=0)
    assert result["n"] == 3
    assert result["sus_by_participant"] == {"P1": 50.0, "P2": 100.0, "P3": 77.5}
    assert result["sus"]["mean"] == pytest.approx(227.5 / 3)
    change = result["confidence_change"]
    assert change["mean"] == pytest.approx(1 / 3)
    assert (change["improved"], change["unchanged"], change["declined"]) == (1, 1, 1)
    assert change["ci95"][0] <= change["mean"] <= change["ci95"][1]
    text = render(result)
    assert "| sus | 3 | 75.83 |" in text
    assert "improved 1, unchanged 1, declined 1" in text


def test_invalid_and_empty_responses() -> None:
    bad = _row("P1", 2, 4, [3] * 10) | {"clarity": "7", "sus_3": ""}
    participants, problems = parse_responses([bad])
    assert participants == []
    assert problems == ["line 2: clarity='7' is not 1-5", "line 2: sus_3='' is not 1-5"]
    empty = analyze([], resamples=10, seed=0)
    assert empty["sus"] == {"n": 0}
    assert "| sus | 0 |" in render(empty)


def test_template_header_matches_columns() -> None:
    with (ROOT_DIR / "eval" / "usability_responses.template.csv").open(newline="", encoding="utf-8") as fh:
        assert tuple(next(csv.reader(fh))) == COLUMNS


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(eval_dir=tmp_path, eval_bootstrap_resamples=100)
    assert main([], settings) == 1
    with settings.usability_responses_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerow(_row("P1", 2, 4, [3] * 10))
    assert main([], settings) == 0
    assert json.loads((settings.eval_results_dir / "usability.json").read_text(encoding="utf-8"))["n"] == 1
    bad = tmp_path / "bad.csv"
    bad.write_text("participant,clarity\nP1,9\n", encoding="utf-8")
    assert main([str(bad)], settings) == 1
    assert "invalid responses" in capsys.readouterr().err
