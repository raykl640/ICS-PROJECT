"""Offline setup (scripts/setup_offline.py) with fake download/which/run tools, and the in-process offline check."""

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.deps import Deps
from backend.app.devstack import fake_deps
from backend.app.offline import OFFLINE_ENV, Step, Tools, cache_models, hf_models, main, pull_ollama, verify_offline
from backend.app.retrieval.meta import REBUILD_COMMAND, IndexMismatchError
from backend.tests.fakes import FakeLLM


class FakeTools:
    """Records downloads and commands; fails the models / commands it is told to."""

    def __init__(
        self, *, ollama: bool = True, fail_models: Sequence[str] = (), fail_commands: Sequence[str] = ()
    ) -> None:
        self.ollama = ollama
        self.fail_models = set(fail_models)
        self.fail_commands = fail_commands
        self.downloads: list[str] = []
        self.commands: list[tuple[list[str], Mapping[str, str] | None]] = []

    def download(self, model: str) -> object:
        self.downloads.append(model)
        if model in self.fail_models:
            raise OSError("network down")
        return f"/cache/{model}"

    def which(self, name: str) -> str | None:
        return f"/usr/bin/{name}" if self.ollama and name == "ollama" else None

    def run(self, command: Sequence[str], env: Mapping[str, str] | None) -> int:
        self.commands.append((list(command), env))
        return 1 if any(part in self.fail_commands for part in command) else 0

    def tools(self) -> Tools:
        return Tools(download=self.download, which=self.which, run=self.run)

    def modules(self) -> list[str]:
        """The `python -m <module>` / ollama commands run, in order."""
        return [cmd[2] if cmd[0] == sys.executable else " ".join(cmd) for cmd, _ in self.commands]


def _settings(tmp_path: Path, chunks: bool = True) -> Settings:
    path = tmp_path / "chunks.json"
    if chunks:
        path.write_text("[]", encoding="utf-8")
    return Settings(chunks_path=path)


def test_all_four_hugging_face_models_are_cached_and_failures_reported() -> None:
    settings = Settings()
    fake = FakeTools(fail_models=[settings.reranker_model])
    steps = cache_models(hf_models(settings), fake.download)
    assert fake.downloads == [
        settings.embedding_model,
        settings.reranker_model,
        settings.translator_sw_en,
        settings.translator_en_sw,
    ]
    assert [step.ok for step in steps] == [True, False, True, True]
    assert "network down" in steps[1].detail


def test_ollama_pull_runs_or_prints_the_command() -> None:
    model = Settings().ollama_model
    present = FakeTools()
    assert pull_ollama(model, present.tools()) == Step(f"ollama pull {model}", True)
    assert present.commands == [(["ollama", "pull", model], None)]
    missing = pull_ollama(model, FakeTools(ollama=False).tools())
    assert not missing.ok
    assert f"ollama pull {model}" in missing.detail
    failing = pull_ollama(model, FakeTools(fail_commands=["pull"]).tools())
    assert not failing.ok


def test_full_setup_order_and_offline_verification_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeTools()
    monkeypatch.setattr("backend.app.offline.get_settings", lambda: _settings(tmp_path, chunks=False))
    assert main([], tools=fake.tools()) == 0
    model = Settings().ollama_model
    assert fake.modules() == [
        f"ollama pull {model}",
        "backend.app.ingestion.build_corpus",
        "backend.app.ingestion.build_index",
        "backend.app.offline",
    ]
    verify_command, verify_env = fake.commands[-1]
    assert verify_command[-1] == "--offline-check"
    assert verify_env is not None
    assert {key: verify_env[key] for key in OFFLINE_ENV} == OFFLINE_ENV
    assert "FAIL" not in capsys.readouterr().out


def test_existing_chunks_skip_the_corpus_build_and_flags_skip_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.app.offline.get_settings", lambda: _settings(tmp_path))
    fake = FakeTools()
    assert main(["--skip-ollama"], tools=fake.tools()) == 0
    assert fake.modules() == ["backend.app.ingestion.build_index", "backend.app.offline"]
    only_verify = FakeTools()
    assert main(["--verify-only", "--skip-ollama"], tools=only_verify.tools()) == 0
    assert only_verify.downloads == []
    assert only_verify.modules() == ["backend.app.offline"]
    assert only_verify.commands[0][0][-2:] == ["--offline-check", "--skip-ollama"]


def test_failures_are_listed_and_stop_dependent_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("backend.app.offline.get_settings", lambda: _settings(tmp_path, chunks=False))
    fake = FakeTools(ollama=False, fail_commands=["backend.app.ingestion.build_corpus"])
    assert main([], tools=fake.tools()) == 1
    assert fake.modules() == ["backend.app.ingestion.build_corpus"]  # no index or verification after a failed build
    out = capsys.readouterr().out
    assert "FAIL ollama pull" in out
    assert "FAIL build corpus" in out


def _deps(tmp_path: Path, llm: FakeLLM | None = None) -> Deps:
    return fake_deps(Settings(), tmp_path / "work", llm=llm or FakeLLM())


def test_offline_check_loads_every_component(tmp_path: Path) -> None:
    steps = verify_offline(_deps(tmp_path), check_ollama=True)
    assert [(step.name, step.ok) for step in steps] == [
        ("load indexes and retrieval models", True),
        ("warm up embedder, cross-encoder and translators", True),
        ("ollama model available", True),
    ]
    assert len(verify_offline(_deps(tmp_path), check_ollama=False)) == 2


def test_offline_check_reports_missing_model_and_stale_index(tmp_path: Path) -> None:
    no_model = verify_offline(_deps(tmp_path, FakeLLM(model_present=False)), check_ollama=True)
    assert not no_model[-1].ok
    assert "ollama pull" in no_model[-1].detail

    def stale() -> None:
        raise IndexMismatchError(f"dense index is stale; rebuild: {REBUILD_COMMAND}")

    broken = Deps(**{**_deps(tmp_path).__dict__, "load_pipeline": stale})
    steps = verify_offline(broken, check_ollama=True)
    assert [step.ok for step in steps] == [False]
    assert REBUILD_COMMAND in steps[0].detail


def test_offline_check_entry_point_uses_the_given_deps(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--offline-check"], deps=_deps(tmp_path)) == 0
    assert capsys.readouterr().out.count("OK") == 3
