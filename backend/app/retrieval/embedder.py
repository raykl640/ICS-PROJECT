"""Text embedding interface. The sentence-transformers implementation is added in M2."""

import hashlib
import re
from typing import Protocol

import numpy as np

_WORD = re.compile(r"\w+")


class Embedder(Protocol):
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return a float32 array of shape (len(texts), dim)."""
        ...


class FakeEmbedder:
    """Deterministic bag-of-hashed-words embedding: shared words give higher similarity."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vector(t) for t in texts]).astype(np.float32)

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for word in _WORD.findall(text.lower()):
            vec[int(hashlib.sha1(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec
