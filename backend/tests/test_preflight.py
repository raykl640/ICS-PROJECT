"""Pre-run checks used by scripts/run.sh and run.ps1: Ollama, model, indexes, frontend build."""

from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.ingestion.build_index import build_indexes
from backend.app.preflight import EXIT_NOT_READY, EXIT_OK, EXIT_OLLAMA_DOWN, check, main
from backend.app.retrieval.meta import REBUILD_COMMAND
from backend.tests.fake_pipeline import ACTS, STORE
from backend.tests.fakes import FakeEmbedder


def _ready(tmp_path: Path) -> Settings:
    """Settings whose chunks, both indexes and frontend build exist under tmp_path."""
    settings = Settings(
        acts=ACTS,
        chunks_path=tmp_path / "chunks.json",
        index_dir=tmp_path / "indexes",
        frontend_dist=tmp_path / "dist",
    )
    STORE.save(settings.chunks_path)
    build_indexes(settings, FakeEmbedder())
    settings.frontend_dist.mkdir()
    (settings.frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    return settings


def test_everything_ready(tmp_path: Path) -> None:
    assert check(_ready(tmp_path), (True, True)) == (EXIT_OK, [])


def test_ollama_down_alone_is_retryable(tmp_path: Path) -> None:
    code, problems = check(_ready(tmp_path), (False, False))
    assert code == EXIT_OLLAMA_DOWN
    assert problems == ["Ollama is not reachable at http://localhost:11434 (start it: ollama serve)"]


def test_missing_model_index_and_frontend_name_their_fixes(tmp_path: Path) -> None:
    settings = Settings(chunks_path=tmp_path / "none.json", frontend_dist=tmp_path / "no-dist")
    code, problems = check(settings, (False, False))
    assert code == EXIT_NOT_READY
    text = "\n".join(problems)
    assert "ollama serve" in text
    assert "python -m backend.app.ingestion.build_corpus" in text
    assert "npm run build" in text
    code, problems = check(settings, (True, False))
    assert f"ollama pull {settings.ollama_model}" in "\n".join(problems)


def test_stale_index_names_the_rebuild_command(tmp_path: Path) -> None:
    settings = _ready(tmp_path)
    (settings.dense_index_dir / "meta.json").unlink()
    code, problems = check(settings, (True, True))
    assert code == EXIT_NOT_READY
    assert REBUILD_COMMAND in problems[0]


def test_cli_prints_address_and_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _ready(tmp_path)
    monkeypatch.setattr("backend.app.preflight.get_settings", lambda: settings)
    assert main(["--address"]) == EXIT_OK
    assert capsys.readouterr().out == f"{settings.api_host} {settings.api_port}\n"
    assert main([], status=(False, False)) == EXIT_OLLAMA_DOWN
    assert "ollama serve" in capsys.readouterr().err
    assert main([], status=(True, True)) == EXIT_OK
    assert "ready" in capsys.readouterr().out
