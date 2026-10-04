"""Protocols for every heavy external dependency; real implementations live in their stage modules, fakes in tests."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt


@runtime_checkable
class Embedder(Protocol):
    """Bi-encoder used for dense indexing and query encoding."""

    dim: int

    def encode(self, texts: list[str]) -> npt.NDArray[np.float32]:
        """Return L2-normalised float32 vectors of shape (len(texts), dim)."""
        ...

    def count_tokens(self, text: str) -> int:
        """Number of model tokens in text, used to size embedding windows."""
        ...


@runtime_checkable
class CrossEncoderLike(Protocol):
    """Cross-encoder that scores (query, doc) pairs jointly."""

    def score(self, query: str, docs: list[str]) -> list[float]:
        """Return one unbounded relevance score per doc; higher is more relevant."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """Streaming text generator (Ollama in production)."""

    def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield generated tokens in order; cancelling the consumer stops generation."""
        ...

    async def health(self) -> bool:
        """True if the backing model is reachable and loaded."""
        ...


@runtime_checkable
class Translator(Protocol):
    """One-direction machine translator (MarianMT in production)."""

    def translate(self, text: str) -> str:
        """Return text translated into the target language."""
        ...

    def translate_batch(self, texts: list[str]) -> list[str]:
        """Translate short texts in one call (one output per input, same order)."""
        ...
