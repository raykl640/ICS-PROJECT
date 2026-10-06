"""Desktop launcher (D34): frozen vs source paths, arguments, Ollama discovery and pull, setup, smoke checks."""

import json
import os
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import platformdirs
import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.config import Settings
from backend.app.desktop import launcher
from backend.app.desktop.launcher import (
    bundle_checks,
    find_ollama,
    hf_cached,
    is_hakiai,
    missing_models,
    online_env,
    parse_args,
    pull_model,
    run_setup,
    self_command,
    smoke_checks,
    wait_for_ollama,
)
from backend.app.devstack import fake_deps
from backend.app.main import create_app
from backend.app.offline import OFFLINE_ENV, Step
from backend.tests.api_support import api_settings
from backend.tests.fakes import DEFAULT_SCRIPT, FakeLLM

MODEL = "mistral:test"


def _frozen(monkeypatch: pytest.MonkeyPatch, meipass: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)


def _ollama(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _ndjson(*lines: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, content="\n".join(json.dumps(line) for line in lines).encode())


def test_source_checkout_paths_are_the_repository() -> None:
    root = Path(config.__file__).resolve().parents[2]
    assert config.resource_root() == root
    assert config.user_data_root(root / "data") == root / "data"


def test_packaged_app_reads_the_bundle_and_writes_to_the_user_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _frozen(monkeypatch, tmp_path / "bundle")
    monkeypatch.setattr(platformdirs, "user_data_dir", lambda name, appauthor: str(tmp_path / name))
    assert config.resource_root() == tmp_path / "bundle"
    assert config.user_data_root(tmp_path / "bundle" / "data") == tmp_path / "HakiAI"


def test_self_command_reruns_the_executable_or_the_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert self_command() == [sys.executable, "-m", "backend.app.desktop"]
    _frozen(monkeypatch, tmp_path)
    assert self_command() == [sys.executable]


def test_arguments() -> None:
    assert not parse_args([]).setup
    assert parse_args(["--setup"]).setup
    assert parse_args(["--self-test", "--no-browser"]).self_test
    with pytest.raises(SystemExit):
        parse_args(["--setup", "--self-test"])


def test_online_env_drops_the_offline_switches_and_quietens_the_hub() -> None:
    env = online_env({**OFFLINE_ENV, "PATH": "/bin", "HAKI_API_PORT": "9000"})
    assert not set(OFFLINE_ENV) & set(env)
    assert env == {"PATH": "/bin", "HAKI_API_PORT": "9000", "HF_HUB_DISABLE_XET": "1", "HF_HUB_VERBOSITY": "error"}


def test_hf_cached_needs_config_and_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    import huggingface_hub

    files = {("m/full", "config.json"), ("m/full", "pytorch_model.bin"), ("m/no-weights", "config.json")}
    monkeypatch.setattr(
        huggingface_hub, "try_to_load_from_cache", lambda repo, name: "/cache" if (repo, name) in files else None
    )
    assert hf_cached("m/full")
    assert not hf_cached("m/no-weights")
    assert not hf_cached("m/absent")


def test_find_ollama_on_path_then_in_the_windows_install_folder(tmp_path: Path) -> None:
    assert find_ollama(lambda name: f"/usr/bin/{name}", {}) == "/usr/bin/ollama"
    assert find_ollama(lambda name: None, {"LOCALAPPDATA": str(tmp_path)}) is None
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    assert find_ollama(lambda name: None, {"LOCALAPPDATA": str(tmp_path)}) == str(exe)
    assert find_ollama(lambda name: None, {}) is None


def test_missing_models() -> None:
    assert missing_models(["a", "b", "c"], lambda model: model == "b") == ["a", "c"]


def test_pull_prints_each_new_progress_line_once() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pull"
        assert json.loads(request.content) == {"model": MODEL}
        return _ndjson(
            {"status": "pulling manifest"},
            {"status": "pulling abc", "total": 4_000_000_000, "completed": 1_000_000_000},
            {"status": "pulling abc", "total": 4_000_000_000, "completed": 1_000_000_001},
            {"status": "success"},
        )

    step = pull_model(Settings(ollama_model=MODEL), seen.append, _ollama(handler))
    assert step.ok
    assert seen == ["pulling manifest", "pulling abc: 25% of 4.0 GB", "success"]


@pytest.mark.parametrize(
    ("response", "detail"),
    [
        (_ndjson({"error": "pull model manifest: file does not exist"}), "Ollama: pull model manifest"),
        (httpx.Response(500, text="boom"), "HTTPStatusError"),
        (httpx.Response(200, text="not json"), "JSONDecodeError"),
    ],
)
def test_pull_failures_name_the_problem(response: httpx.Response, detail: str) -> None:
    step = pull_model(Settings(ollama_model=MODEL), lambda text: None, _ollama(lambda request: response))
    assert not step.ok
    assert step.detail.startswith(detail)


def test_setup_caches_models_and_pulls_only_when_ollama_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    downloaded: list[str] = []
    printed: list[str] = []
    settings = Settings(ollama_model=MODEL)
    monkeypatch.setattr(launcher, "ollama_status", lambda s: (False, False))
    assert run_setup(settings, downloaded.append, printed.append) == 0
    assert len(downloaded) == 4
    assert "was not downloaded" in printed[0]

    monkeypatch.setattr(launcher, "ollama_status", lambda s: (True, False))
    monkeypatch.setattr(launcher, "pull_model", lambda s, out: Step("pull", False, "offline"))
    assert run_setup(settings, downloaded.append, printed.append) == 1


def test_wait_for_ollama_polls_until_it_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    answers = iter([(False, False), (False, False), (True, True)])
    assert wait_for_ollama(Settings(), lambda: next(answers)) == (True, True)
    assert wait_for_ollama(Settings(ollama_start_wait_s=1e-9), lambda: (False, False)) == (False, False)


@pytest.mark.parametrize(
    ("handler", "expected"),
    [
        (lambda request: httpx.Response(503, json={"status": "degraded", "indexes_loaded": False}), True),
        (lambda request: httpx.Response(200, json={"status": "ok"}), False),
        (lambda request: httpx.Response(200, text="<html>"), False),
    ],
)
def test_is_hakiai_recognises_its_own_health_body(
    handler: Callable[[httpx.Request], httpx.Response], expected: bool
) -> None:
    assert is_hakiai("http://127.0.0.1:8000", _ollama(handler)) is expected


def test_is_hakiai_false_when_nothing_listens() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert not is_hakiai("http://127.0.0.1:8000", _ollama(refuse))


def test_smoke_checks_pass_on_the_fake_stack(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>HakiAI</title>", encoding="utf-8")
    deps = fake_deps(api_settings(tmp_path, frontend_dist=dist), tmp_path, llm=FakeLLM(list(DEFAULT_SCRIPT)))
    with TestClient(create_app(deps)) as client:
        steps = smoke_checks(client)
    assert [step.name for step in steps if not step.ok] == []
    assert [step.name for step in steps] == ["health", "frontend served", "question accepted", "answer streamed"]


def test_bundle_checks_report_a_missing_corpus_and_frontend(tmp_path: Path) -> None:
    settings = Settings(chunks_path=tmp_path / "chunks.json", frontend_dist=tmp_path / "dist")
    steps = bundle_checks(settings)
    assert [step.ok for step in steps] == [False, False]
    assert "chunks.json" in steps[0].detail


def test_launch_reuses_a_running_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(launcher, "is_hakiai", lambda url: True)
    monkeypatch.setattr(webbrowser, "open", opened.append)
    assert launcher.launch(Settings(api_port=8123), open_browser=True) == 0
    assert opened == ["http://127.0.0.1:8123"]


def test_launch_stops_when_setup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(launcher, "is_hakiai", lambda url: False)
    monkeypatch.setattr(launcher, "ensure_ollama", lambda s, open_browser: (True, False))
    monkeypatch.setattr(launcher, "hf_cached", lambda model: True)

    def fail(command: list[str], env: dict[str, str], check: bool) -> Any:
        calls.append(command)
        assert not set(OFFLINE_ENV) & set(env)
        return type("Done", (), {"returncode": 1})()

    monkeypatch.setattr(subprocess, "run", fail)
    assert launcher.launch(Settings(), open_browser=False) == 1
    assert calls == [[*self_command(), "--setup"]]


def test_ensure_ollama_explains_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(launcher, "ollama_status", lambda s: (False, False))
    monkeypatch.setattr(launcher, "find_ollama", lambda which, env: None)
    monkeypatch.setattr(webbrowser, "open", opened.append)
    settings = Settings()
    assert launcher.ensure_ollama(settings, open_browser=True) == (False, False)
    assert settings.ollama_download_url in capsys.readouterr().out
    assert opened == [settings.ollama_download_url]


def test_ensure_ollama_starts_an_installed_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    started: list[tuple[str, Path]] = []
    answers = iter([(False, False), (True, True)])
    monkeypatch.setattr(launcher, "ollama_status", lambda s: next(answers))
    monkeypatch.setattr(launcher, "find_ollama", lambda which, env: "/opt/ollama")
    monkeypatch.setattr(launcher, "start_ollama", lambda exe, log: started.append((exe, log)))
    settings = Settings(ollama_log_path=tmp_path / "ollama.log")
    assert launcher.ensure_ollama(settings, open_browser=False) == (True, True)
    assert started == [("/opt/ollama", tmp_path / "ollama.log")]


def test_main_dispatches_setup_and_sets_offline_mode_for_a_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [*OFFLINE_ENV, "HAKI_LOG_LEVEL"]:  # set then delete, so the teardown restores the original state
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    monkeypatch.setattr(launcher, "run_setup", lambda settings, download, out: 7)
    assert launcher.main(["--setup"]) == 7
    monkeypatch.setattr(launcher, "launch", lambda settings, open_browser: 0 if not open_browser else 1)
    assert launcher.main(["--no-browser"]) == 0
    assert all(os.environ[key] == value for key, value in OFFLINE_ENV.items())
    assert os.environ["HAKI_LOG_LEVEL"] == "WARNING"
