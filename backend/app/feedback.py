"""Append-only feedback log (JSONL). Callers pass ids, ratings and flags only, never question/answer/chunk text."""

import json
import sys
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

_PROCESS_LOCK = threading.Lock()


@contextmanager
def _exclusive(handle: TextIO) -> Iterator[None]:
    """flock across processes on POSIX; on Windows (no fcntl) an in-process lock, enough for one server process."""
    if sys.platform == "win32":
        with _PROCESS_LOCK:
            yield
        return
    import fcntl

    fcntl.flock(handle, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)


def append_feedback(path: Path, record: Mapping[str, object]) -> None:
    """Append one JSON line under an exclusive lock, creating the parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as handle, _exclusive(handle):
        handle.write(line)
        handle.flush()
