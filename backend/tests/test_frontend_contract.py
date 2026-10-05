"""Files shared with the frontend stay in step with config.py (the frontend cannot read Settings)."""

import base64
import hashlib
import json
import re
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.web import PREPAINT_SCRIPT_SHA256

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_limits_mirror_settings() -> None:
    limits = json.loads((ROOT / "frontend" / "src" / "limits.json").read_text(encoding="utf-8"))
    settings = Settings()
    assert limits == {
        "max_question_chars": settings.max_question_chars,
        "max_comment_chars": settings.max_comment_chars,
    }


def test_referral_resources_hold_only_verified_named_entries() -> None:
    data = json.loads((ROOT / "config" / "referral_resources.json").read_text(encoding="utf-8"))
    for entry in data["entries"]:
        assert entry["name"].strip()
        assert isinstance(entry["verified"], bool)


def _inline_script_hash(html_path: Path) -> str:
    scripts = re.findall(r"<script>(.*?)</script>", html_path.read_text(encoding="utf-8"), re.S)
    assert len(scripts) == 1, "index.html must have exactly one inline script (the pre-paint settings script)"
    return base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode("ascii")


def test_csp_hash_matches_the_prepaint_script() -> None:
    assert _inline_script_hash(ROOT / "frontend" / "index.html") == PREPAINT_SCRIPT_SHA256


def test_built_index_keeps_the_prepaint_script_byte_identical() -> None:
    built = ROOT / "frontend" / "dist" / "index.html"
    if not built.exists():
        pytest.skip("frontend not built")
    assert _inline_script_hash(built) == PREPAINT_SCRIPT_SHA256
