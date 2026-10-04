"""Reciprocal Rank Fusion (ARCHITECTURE.md §5.1): score = sum over lists of 1 / (k + rank), ranks 1-indexed."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Fused:
    """A fused candidate: its RRF score and its 1-indexed rank in each input list (None if absent)."""

    chunk_id: str
    score: float
    ranks: tuple[int | None, ...]


def rrf(*ranked: Sequence[str], k: int) -> list[Fused]:
    """Fuse ranked id lists; order by score desc, then best single-list rank, then chunk_id (deterministic)."""
    ranks: dict[str, list[int | None]] = {}
    for list_no, ids in enumerate(ranked):
        for rank, chunk_id in enumerate(ids, start=1):
            slots = ranks.setdefault(chunk_id, [None] * len(ranked))
            if slots[list_no] is None:
                slots[list_no] = rank
    fused = [
        Fused(chunk_id, sum(1 / (k + r) for r in slots if r is not None), tuple(slots))
        for chunk_id, slots in ranks.items()
    ]
    return sorted(fused, key=lambda f: (-f.score, min(r for r in f.ranks if r is not None), f.chunk_id))
