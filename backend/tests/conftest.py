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
    yield root
