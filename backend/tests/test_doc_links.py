"""Docs acceptance: scripts/check_links.py finds no broken relative links or anchors, and catches a broken one."""

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_links", ROOT / "scripts" / "check_links.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_docs_have_no_broken_links() -> None:
    assert _checker().broken_links(ROOT) == []


def test_checker_reports_missing_files_and_headings_but_ignores_code_and_urls(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "B.md").write_text("# Real Heading (v1)\n", encoding="utf-8")
    (tmp_path / "A.md").write_text(
        "[ok](docs/B.md#real-heading-v1) [web](https://example.org/x) [self](#top)\n# Top\n"
        "[gone](docs/C.md) [bad](docs/B.md#nope) `[code](missing.md)`\n```\n[fenced](missing.md)\n```\n",
        encoding="utf-8",
    )
    assert _checker().broken_links(tmp_path) == [
        "A.md: docs/C.md (no such file)",
        "A.md: docs/B.md#nope (no such heading)",
    ]
