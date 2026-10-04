import asyncio
import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.evaluation.latency import main, run_latency, summarize, time_stream
from backend.app.generation.llm import OllamaUnavailable
from backend.tests.fake_pipeline import ACTS, fake_pipeline
from backend.tests.fakes import FakeLLM

QUESTIONS = ("qxzv blorp", "my employer fired me and did not pay my wages")


def _settings(tmp_path: Path) -> Settings:
    return Settings(acts=ACTS, eval_dir=tmp_path / "eval", relevance_threshold=1.0)


def test_time_stream_counts_tokens() -> None:
    ttft, total, tokens = asyncio.run(time_stream(FakeLLM(["a", "b", "c"]), "p"))
    assert tokens == 3
    assert ttft is not None
    assert 0 <= ttft <= total
    assert asyncio.run(time_stream(FakeLLM([]), "p"))[0] is None


def test_runs_skip_null_questions_and_use_the_real_prompt(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    llm = FakeLLM()
    runs = asyncio.run(run_latency(fake_pipeline(tmp_path / "s", settings), llm, QUESTIONS, 3, settings))
    assert [r["cold"] for r in runs] == [True, False, False]
    assert {r["question_index"] for r in runs} == {1}
    assert len(llm.prompts) == 3
    assert "USER QUESTION" in llm.prompts[0]
    summary = summarize(runs)
    assert summary["warm_runs"] == 2
    assert summary["cold"] == runs[0]
    assert summary["ttft_s"]["p50"] <= summary["total_s"]["p95"]
    assert summarize(runs[:1])["warm_runs"] == 1  # a single run is used as warm too
    with pytest.raises(ValueError):
        asyncio.run(run_latency(fake_pipeline(tmp_path / "t", settings), llm, QUESTIONS[:1], 1, settings))


def test_cli_saves_hardware_and_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = _settings(tmp_path)
    pipeline = fake_pipeline(tmp_path / "s", settings)
    assert main(["-n", "2"], settings, pipeline, FakeLLM()) == 0
    saved = json.loads((settings.eval_results_dir / "latency.json").read_text(encoding="utf-8"))
    assert {"cpu", "ram", "cores", "llm_model", "num_ctx"} <= set(saved["hardware"])
    assert len(saved["runs"]) == 2
    assert "warm first token (n=1)" in capsys.readouterr().out
    assert main(["-n", "1"], settings, pipeline, FakeLLM(fail_with=OllamaUnavailable("down"))) == 1
