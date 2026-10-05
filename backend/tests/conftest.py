"""Default tests never write into the real data/ directory: every Settings() they build points its output paths at a
temp dir (explicit keyword arguments still win). Tests marked `real` keep the real paths: they read real indexes."""

from collections.abc import Iterator
from pathlib import Path

import pytest

_OUTPUT_PATHS = {
    "HAKI_PROCESSED_DIR": "processed",
    "HAKI_INDEX_DIR": "indexes",
    "HAKI_CHUNKS_PATH": "processed/chunks.json",
    "HAKI_PARSE_REPORT_PATH": "processed/parse_report.md",
    "HAKI_FEEDBACK_PATH": "feedback.jsonl",
    "HAKI_MANIFEST_PATH": "corpus_manifest.json",
    "HAKI_APP_DB_PATH": "app.db",
}
# In-process test clients send Host "testserver" (TestClient) or "test" (api_support.call); argon2 kept cheap.
_TEST_ENV = {
    "HAKI_ALLOWED_HOSTS": '["127.0.0.1", "localhost", "testserver", "test"]',
    "HAKI_ARGON2_TIME_COST": "1",
    "HAKI_ARGON2_MEMORY_KIB": "8",
    "HAKI_ARGON2_PARALLELISM": "1",
}


@pytest.fixture(autouse=True)
def _isolated_data_dir(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path | None]:
    """Redirect the data output paths of non-real tests to a fresh temp dir."""
    if request.node.get_closest_marker("real"):
        yield None
        return
    root = tmp_path_factory.mktemp("data")
    for name, relative in _OUTPUT_PATHS.items():
        monkeypatch.setenv(name, str(root / relative))
    for name, value in _TEST_ENV.items():
        monkeypatch.setenv(name, value)
    yield root
