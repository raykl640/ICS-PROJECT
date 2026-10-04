"""Deterministic fakes for the Protocols in backend.app.interfaces (and extract.OcrEngine); no models, no network."""

import hashlib
import re
from collections.abc import AsyncIterator, Mapping
from pathlib import Path

import numpy as np
import numpy.typing as npt

_WORD = re.compile(r"\w+")

# Headers are deliberately split across tokens, as a real token stream would.
DEFAULT_SCRIPT: tuple[str, ...] = (
    "## RIGHTS",
    " EXPLA",
    "NATION\nYou have rights under Sample Act, Section 12.\n\n#",
    "# RECOMMENDED",
    " STEPS\n1. Write to the other party.\n\n",
    "## FORMAL LE",
    "TTER\nDear Sir or Madam,\n",
)


class FakeEmbedder:
    """Bag of hashed words, L2-normalised: shared words give higher similarity; tokens are words."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def encode(self, texts: list[str]) -> npt.NDArray[np.float32]:
        """Embed each text as a normalised hashed word-count vector."""
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in _WORD.findall(text.lower()):
                vectors[row, int(hashlib.sha1(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        np.divide(vectors, norms, out=vectors, where=norms > 0)
        return vectors

    def count_tokens(self, text: str) -> int:
        """Count words as tokens."""
        return len(_WORD.findall(text))


class FakeReranker:
    """Scores by number of distinct query words present in the doc; 0 means no overlap."""

    def score(self, query: str, docs: list[str]) -> list[float]:
        """Return the word-overlap count per doc."""
        terms = set(_WORD.findall(query.lower()))
        return [float(len(terms & set(_WORD.findall(doc.lower())))) for doc in docs]


class FakeLLM:
    """Streams a fixed token script and records every prompt it receives."""

    def __init__(self, tokens: list[str] | None = None, healthy: bool = True) -> None:
        self.tokens = list(DEFAULT_SCRIPT) if tokens is None else tokens
        self.healthy = healthy
        self.prompts: list[str] = []

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Record the prompt, then yield the scripted tokens."""
        self.prompts.append(prompt)
        for token in self.tokens:
            yield token

    async def health(self) -> bool:
        """Return the configured health flag."""
        return self.healthy


class FakeTranslator:
    """Replaces dictionary words and prefixes "[tag]" so tests can see a translation happened."""

    def __init__(self, tag: str = "sw", dictionary: Mapping[str, str] | None = None) -> None:
        self.tag = tag
        self.dictionary = {k.lower(): v for k, v in (dictionary or {}).items()}

    def translate(self, text: str) -> str:
        """Return the tagged, word-substituted text."""
        swapped = _WORD.sub(lambda m: self.dictionary.get(m.group().lower(), m.group()), text)
        return f"[{self.tag}] {swapped}"

    def translate_batch(self, texts: list[str]) -> list[str]:
        """Translate each text independently."""
        return [self.translate(t) for t in texts]


class FakeOcrEngine:
    """Returns canned text per page with a fixed confidence; records which pages were OCR'd."""

    def __init__(self, texts: Mapping[int, str], confidence: float) -> None:
        self.texts = dict(texts)
        self.confidence = confidence
        self.calls: list[int] = []

    def page_text(self, pdf: Path, page_no: int) -> tuple[str, float]:
        self.calls.append(page_no)
        return self.texts.get(page_no, ""), self.confidence
