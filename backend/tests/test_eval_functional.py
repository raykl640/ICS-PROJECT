import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import ROOT_DIR, Settings
from backend.app.evaluation.functional import (
    FUNCTIONAL_QUERIES,
    FUNCTIONAL_RECORDS,
    FunctionalQuery,
    main,
    read_events,
    run_all,
    run_query,
)
from backend.app.generation.llm import OllamaUnavailable
from backend.tests.api_support import EN_QUESTION, GARBAGE, SW_QUESTION, FakeClock, make_app, sw_translators
from backend.tests.fakes import FakeLLM

EN = FunctionalQuery(id="F01", question=EN_QUESTION, lang="en", category="employment")
NULL = FunctionalQuery(id="F02", question=GARBAGE, lang="en", category="out_of_corpus", expect_null=True)
SW = FunctionalQuery(id="F03", question=SW_QUESTION, lang="sw", category="employment")


def test_read_events_parses_named_events_and_skips_comments() -> None:
    lines = [": ping", "event: token", 'data: {"text": "a"}', "", 'data: {"x": 1}']
    assert list(read_events(lines)) == [("token", {"text": "a"}), ("message", {"x": 1})]


def test_shipped_functional_questions_match_the_milestone_mix() -> None:
    queries = FUNCTIONAL_QUERIES.validate_json((ROOT_DIR / "eval" / "queries_functional.json").read_bytes())
    assert len(queries) == 20
    assert sum(q.lang == "sw" for q in queries) == 5
    assert sum(q.expect_null for q in queries) == 3
    assert {q.category for q in queries} >= {
        "employment",
        "tenancy",
        "consumer",
        "police",
        "traffic",
        "land",
        "criminal_procedure",
    }
    assert len({q.id for q in queries}) == 20


def test_answer_null_and_kiswahili_records(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    app = make_app(tmp_path, FakeLLM(), rate_limit_per_min=100, **sw_translators())
    with TestClient(app) as client:
        en, null, sw = run_all(client, [EN, NULL, SW])
    assert en.error is None
    assert not en.null_response
    assert en.answer_en.startswith("## RIGHTS EXPLANATION")
    assert en.tokens > 1
    assert en.ttft_s is not None
    assert en.total_s >= en.ttft_s
    assert en.format_ok
    assert en.sources
    assert en.sources[0].rank == 1
    assert en.sources[0].text
    assert en.disclaimer
    assert en.citation_check.verified or en.citation_check.unmatched
    assert null.null_response
    assert null.sources == []
    assert null.answer_en == ""
    assert null.disclaimer
    assert sw.sections_user is not None
    assert sw.sections_user["rights"].startswith("[sw]")
    assert sw.warnings  # translation note on every Kiswahili answer
    assert "[3/3] F03" in capsys.readouterr().out


def test_rate_limit_is_waited_out(tmp_path: Path) -> None:
    clock = FakeClock()
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        clock.now += seconds

    app = make_app(tmp_path, FakeLLM(), clock=clock, rate_limit_per_min=1)
    with TestClient(app) as client:
        first = run_query(client, NULL, sleep)
        second = run_query(client, NULL, sleep)
    assert first.error is None
    assert second.error is None
    assert waits and waits[0] > 0


def test_stream_failure_is_recorded_and_main_exits_1(tmp_path: Path) -> None:
    settings = Settings(eval_dir=tmp_path / "eval")
    settings.eval_dir.mkdir()
    settings.functional_queries_path.write_text(json.dumps([EN.model_dump(), NULL.model_dump()]), encoding="utf-8")
    app = make_app(tmp_path, FakeLLM(fail_with=OllamaUnavailable("down")), rate_limit_per_min=100)
    assert main(["--only", "F01"], settings, TestClient(app)) == 1
    records = FUNCTIONAL_RECORDS.validate_json((settings.eval_results_dir / "functional.json").read_bytes())
    assert [r.id for r in records] == ["F01"]
    assert records[0].error == "stream llm_unavailable"


def test_main_saves_records_and_refuses_an_unhealthy_api(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(eval_dir=tmp_path / "eval")
    settings.eval_dir.mkdir()
    settings.functional_queries_path.write_text(json.dumps([NULL.model_dump()]), encoding="utf-8")
    out = tmp_path / "f.json"
    assert main(["--out", str(out)], settings, TestClient(make_app(tmp_path, FakeLLM()))) == 0
    assert FUNCTIONAL_RECORDS.validate_json(out.read_bytes())[0].null_response
    assert main([], settings, TestClient(make_app(tmp_path, FakeLLM(healthy=False)))) == 2
    assert "not healthy" in capsys.readouterr().err


def test_query_validation_error_is_recorded(tmp_path: Path) -> None:
    too_long = FunctionalQuery(id="X", question="x" * 2000, lang="en", category="c")
    with TestClient(make_app(tmp_path, FakeLLM()), raise_server_exceptions=False) as client:
        record = run_query(client, too_long)
    assert record.error is not None
    assert record.error.startswith("HTTP 422")
