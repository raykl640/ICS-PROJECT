"""FAISS IndexFlatL2 over normalised window vectors; results are aggregated to parent chunks (best window wins)."""

import json
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import numpy.typing as npt

from backend.app.interfaces import Embedder
from backend.app.models import LegalChunk
from backend.app.retrieval.meta import IndexMeta, now_utc, read_meta, reset_dir, write_meta
from backend.app.retrieval.windows import WindowSpec, make_windows

INDEX_FILE = "index.faiss"
ID_MAP_FILE = "id_map.json"


class DenseIndex:
    """Window vectors plus the parallel id map window position -> (chunk_id, act_slug)."""

    def __init__(self, index: Any, window_chunk_ids: list[str], window_act_slugs: list[str], meta: IndexMeta) -> None:
        self.index = index
        self.window_chunk_ids = window_chunk_ids
        self.window_act_slugs = window_act_slugs
        self.meta = meta
        self._act_windows: dict[str, npt.NDArray[np.int64]] = {
            act: np.flatnonzero(np.asarray(window_act_slugs) == act).astype(np.int64) for act in set(window_act_slugs)
        }

    @classmethod
    def build(
        cls,
        chunks: Sequence[LegalChunk],
        embedder: Embedder,
        *,
        spec: WindowSpec,
        model_name: str,
        corpus_hash: str,
    ) -> "DenseIndex":
        """Embed every window of every chunk (caller passes non-repealed chunks only)."""
        if not chunks:
            raise ValueError("no chunks to index")
        texts: list[str] = []
        chunk_ids: list[str] = []
        act_slugs: list[str] = []
        for chunk in chunks:
            windows = make_windows(chunk, spec)
            texts += windows
            chunk_ids += [chunk.chunk_id] * len(windows)
            act_slugs += [chunk.act_slug] * len(windows)
        index = faiss.IndexFlatL2(embedder.dim)
        index.add(np.ascontiguousarray(embedder.encode(texts), dtype=np.float32))
        meta = IndexMeta(
            kind="dense",
            corpus_hash=corpus_hash,
            chunks=len(chunks),
            entries=len(texts),
            built_at=now_utc(),
            model=model_name,
            dim=embedder.dim,
        )
        return cls(index, chunk_ids, act_slugs, meta)

    def save(self, directory: Path) -> None:
        """Replace directory with index.faiss, id_map.json and meta.json."""
        reset_dir(directory)
        faiss.write_index(self.index, str(directory / INDEX_FILE))
        id_map = {"chunk_ids": self.window_chunk_ids, "act_slugs": self.window_act_slugs}
        (directory / ID_MAP_FILE).write_text(json.dumps(id_map), encoding="utf-8")
        write_meta(directory, self.meta)

    @classmethod
    def load(cls, directory: Path, *, model_name: str, corpus_hash: str) -> "DenseIndex":
        """Load a saved index; IndexMismatchError if missing or built from another model or corpus."""
        meta = read_meta(directory, "dense", corpus_hash, model_name)
        id_map = json.loads((directory / ID_MAP_FILE).read_text(encoding="utf-8"))
        return cls(faiss.read_index(str(directory / INDEX_FILE)), id_map["chunk_ids"], id_map["act_slugs"], meta)

    def search(
        self, query_vec: npt.NDArray[np.float32], k: int, acts: Collection[str] | None = None
    ) -> list[tuple[str, float]]:
        """Top-k parent chunks as (chunk_id, squared L2 distance), ascending; acts restricts to those act_slugs.

        Empty or None acts means the whole corpus. Fewer than k results are returned when the filter leaves fewer.
        """
        query = np.ascontiguousarray(query_vec, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self.index.d:
            raise ValueError(f"query dimension {query.shape[1]} != index dimension {self.index.d}")
        if not acts:
            return self._ranked(query, self.index.ntotal, None, k)
        allowed = [self._act_windows[a] for a in acts if a in self._act_windows]
        if not allowed:
            return []
        selector = faiss.IDSelectorBatch(np.concatenate(allowed))
        params = faiss.SearchParameters()
        params.sel = selector
        return self._ranked(query, sum(len(a) for a in allowed), params, k)

    def _ranked(self, query: npt.NDArray[np.float32], fetch: int, params: Any, k: int) -> list[tuple[str, float]]:
        """Search every candidate window (flat index is exhaustive anyway) and keep each parent's best window."""
        distances, positions = self.index.search(query, fetch, params=params)
        best: dict[str, float] = {}
        for distance, position in zip(distances[0], positions[0], strict=True):
            if position >= 0:
                best.setdefault(self.window_chunk_ids[position], float(distance))
        return list(best.items())[:k]
