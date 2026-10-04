"""Chunk store: every LegalChunk (repealed included) keyed by chunk_id, loaded from chunks.json."""

import hashlib
import json
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path

from pydantic import TypeAdapter

from backend.app.models import LegalChunk

_CHUNK_LIST = TypeAdapter(list[LegalChunk])


class ChunkStore:
    """Validated, ordered chunk collection with lookup by id and a content hash for index staleness checks."""

    def __init__(self, chunks: Iterable[LegalChunk]) -> None:
        self._chunks: dict[str, LegalChunk] = {}
        for chunk in chunks:
            if chunk.chunk_id in self._chunks:
                raise ValueError(f"duplicate chunk_id {chunk.chunk_id!r}")
            self._chunks[chunk.chunk_id] = chunk

    @classmethod
    def load(cls, path: Path) -> "ChunkStore":
        """Read and validate chunks.json (raises ValueError/ValidationError on bad content, OSError if missing)."""
        return cls(_CHUNK_LIST.validate_json(path.read_bytes()))

    def save(self, path: Path) -> None:
        """Write chunks.json in document order."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([c.model_dump() for c in self._chunks.values()], indent=1, ensure_ascii=False)
        path.write_text(payload + "\n", encoding="utf-8")

    def __len__(self) -> int:
        return len(self._chunks)

    def __contains__(self, chunk_id: object) -> bool:
        return chunk_id in self._chunks

    def all(self) -> list[LegalChunk]:
        """Every chunk in document order."""
        return list(self._chunks.values())

    def indexable(self) -> list[LegalChunk]:
        """Chunks that go into the search indexes (repealed ones stay in the store only)."""
        return [c for c in self._chunks.values() if not c.repealed]

    def get(self, ids: Iterable[str]) -> list[LegalChunk]:
        """Chunks for ids in the given order; KeyError for an unknown id."""
        return [self._chunks[chunk_id] for chunk_id in ids]

    @cached_property
    def corpus_hash(self) -> str:
        """sha256 of the canonical JSON of all chunks (sorted keys, compact), independent of file formatting."""
        canonical = json.dumps(
            [c.model_dump() for c in self._chunks.values()], sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
