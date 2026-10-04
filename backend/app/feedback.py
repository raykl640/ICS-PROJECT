"""Append-only feedback log (JSONL). Callers pass ids, ratings and flags only, never question/answer/chunk text."""

import fcntl
import json
from collections.abc import Mapping
from pathlib import Path


def append_feedback(path: Path, record: Mapping[str, object]) -> None:
    """Append one JSON line under an exclusive file lock, creating the parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.flush()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
