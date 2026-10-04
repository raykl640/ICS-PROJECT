import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.config import ROOT_DIR, Settings
from backend.app.evaluation.schema import (
    load_ground_truth,
    schema_main,
    validate_ground_truth,
    validate_main,
)
from backend.tests.fake_pipeline import ACTS, STORE


def _entry(eid: str = "R01", question: str = "fired without notice", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": eid,
        "question": question,
        "lang": "en",
        "category": "employment",
        "relevant": [{"act": "Sample Employment Act", "section": "4"}],
    }
    return base | overrides


def test_valid_entries_resolve_by_name_slug_prefix_int_and_schedule() -> None:
    raw = [
        _entry(),
        _entry(
            "R02",
            "rights of arrested people",
            category="police",
            relevant=[
                {"act": "sample-constitution", "section": "Article 49"},
                {"act": "Sample Constitution", "section": "First Schedule"},
                {"act": "sample employment act", "section": 41},
            ],
        ),
    ]
    result = validate_ground_truth(raw, STORE, ACTS)
    assert result.ok, result.problems
    assert result.entries[0].relevant_ids == {"sample-employment-act-4"}
    assert result.entries[1].relevant_ids == {
        "sample-constitution-49",
        "sample-constitution-sch1",
        "sample-employment-act-41",
    }


def test_unknown_act_section_and_repealed_targets_are_listed() -> None:
    raw = [
        _entry(
            relevant=[
                {"act": "Patent Act", "section": "3"},
                {"act": "Sample Tenancy Act", "section": "99"},
                {"act": "Sample Tenancy Act", "section": "6"},
            ]
        )
    ]
    result = validate_ground_truth(raw, STORE, ACTS)
    assert not result.ok
    assert result.entries == []
    assert result.problems == [
        "R01: unknown act 'Patent Act'",
        "R01: Sample Tenancy Act '99' is not in the chunk store",
        "R01: Sample Tenancy Act '6' (sample-tenancy-act-6) is repealed and not indexed",
    ]


def test_schema_errors_and_duplicates_are_reported() -> None:
    blank = validate_ground_truth([_entry(question="   ", relevant=[])], STORE, ACTS)
    assert any("question" in p for p in blank.problems)
    assert any("relevant" in p for p in blank.problems)
    wrong_lang = validate_ground_truth([_entry(lang="fr")], STORE, ACTS)
    assert any("lang" in p for p in wrong_lang.problems)
    dupes = validate_ground_truth([_entry(), _entry("r01", "Fired without notice")], STORE, ACTS)
    assert dupes.problems == ["duplicate id 'r01'", "duplicate question 'fired without notice'"]
    assert validate_ground_truth([], STORE, ACTS).problems == ["no entries"]
    assert validate_ground_truth({"not": "a list"}, STORE, ACTS).problems


def test_shipped_template_is_empty_and_fails_validation() -> None:
    template = json.loads((ROOT_DIR / "eval" / "ground_truth.template.json").read_text(encoding="utf-8"))
    assert len(template) == 15
    assert all(e["question"] == "" and e["category"] == "" for e in template)
    assert all(ref == {"act": "", "section": ""} for e in template for ref in e["relevant"])
    assert not validate_ground_truth(template, STORE, ACTS).ok


def test_load_reports_missing_and_malformed_files(tmp_path: Path) -> None:
    assert "does not exist" in load_ground_truth(tmp_path / "nope.json", STORE, ACTS).problems[0]
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert "invalid JSON" in load_ground_truth(bad, STORE, ACTS).problems[0]


def _settings(tmp_path: Path) -> Settings:
    STORE.save(tmp_path / "chunks.json")
    return Settings(chunks_path=tmp_path / "chunks.json", acts=ACTS, eval_dir=tmp_path)


def test_validate_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = _settings(tmp_path)
    settings.ground_truth_path.write_text(json.dumps([_entry()]), encoding="utf-8")
    assert validate_main([], settings) == 0
    assert "OK: 1 queries, 1 relevant chunks, categories: employment" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([_entry(relevant=[{"act": "Nope", "section": "1"}])]), encoding="utf-8")
    assert validate_main([str(bad)], settings) == 1
    assert "unknown act 'Nope'" in capsys.readouterr().err
    assert validate_main([], settings.model_copy(update={"chunks_path": tmp_path / "missing.json"})) == 2


def test_schema_cli_prints_json_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert schema_main([]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema["type"] == "array"
    assert "GroundTruthEntry" in json.dumps(schema)
