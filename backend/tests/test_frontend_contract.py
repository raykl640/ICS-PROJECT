"""Files shared with the frontend stay in step with config.py (the frontend cannot read Settings)."""

import json
from pathlib import Path

from backend.app.config import Settings

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
