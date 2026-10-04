"""Shared plumbing for the eval CLIs: JSON files, offline model mode, and question translation for Kiswahili entries."""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.lang.service import load_language_service
from backend.app.models import UserLanguage

ToEnglish = Callable[[str, UserLanguage], str]


def read_json(path: Path) -> Any:
    """Parsed JSON from a UTF-8 file."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    """Pretty UTF-8 JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def use_offline_models() -> None:
    """Load models from the local cache only, as the API does (scripts/setup_offline.py fills it once)."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def marian_to_english(settings: Settings) -> ToEnglish:
    """Question translator used by the API (sw→en Marian, loaded lazily on the first Kiswahili question)."""
    language = load_language_service(settings)
    return lambda question, lang: language.prepare_query(question, lang).english
