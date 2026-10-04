"""Index metadata (meta.json) shared by the dense and sparse indexes, and the stale-index error."""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

REBUILD_COMMAND = "python -m backend.app.ingestion.build_index"
META_FILE = "meta.json"


class IndexMismatchError(RuntimeError):
    """An index on disk is missing, unreadable, or was built from another corpus or model."""


class IndexMeta(BaseModel):
    """What an index was built from; checked on load so a stale index is never searched."""

    kind: Literal["dense", "sparse"]
    corpus_hash: str
    chunks: int
    entries: int
    built_at: str
    model: str = ""
    dim: int = 0


def now_utc() -> str:
    """Build timestamp recorded in meta.json (informational only, never compared)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def reset_dir(directory: Path) -> None:
    """Replace directory with an empty one; each index owns its directory outright."""
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)


def write_meta(directory: Path, meta: IndexMeta) -> None:
    """Write meta.json into an index directory."""
    (directory / META_FILE).write_text(meta.model_dump_json(indent=1) + "\n", encoding="utf-8")


def read_meta(directory: Path, kind: str, corpus_hash: str, model: str = "") -> IndexMeta:
    """Read meta.json and check it matches the expected corpus (and model); raise IndexMismatchError otherwise."""
    path = directory / META_FILE
    try:
        meta = IndexMeta.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as err:
        raise IndexMismatchError(f"no readable {kind} index at {directory}; build it with: {REBUILD_COMMAND}") from err
    expected = {"kind": kind, "corpus_hash": corpus_hash, "model": model}
    found = {"kind": meta.kind, "corpus_hash": meta.corpus_hash, "model": meta.model}
    stale = [f"{key} {found[key]!r} != expected {expected[key]!r}" for key in expected if found[key] != expected[key]]
    if stale:
        raise IndexMismatchError(
            f"{kind} index at {directory} is stale ({'; '.join(stale)}); rebuild: {REBUILD_COMMAND}"
        )
    return meta


def dir_bytes(directory: Path) -> int:
    """Total size of the files in an index directory."""
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
