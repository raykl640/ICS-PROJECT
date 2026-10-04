"""Deterministic fakes for the Protocols in backend.app.interfaces (and extract.OcrEngine); no models, no network."""

import asyncio
import hashlib
import json
import re
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import httpx
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
    """Streams a fixed token script and records every prompt; can pause, fail, run slowly or report itself down.

    pause_after=n waits on `resume` before token n; `cancelled` turns True if the stream is cancelled or closed early.
    """

    def __init__(
        self,
        tokens: list[str] | None = None,
        healthy: bool = True,
        *,
        model_present: bool = True,
        pause_after: int | None = None,
        fail_with: Exception | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.tokens = list(DEFAULT_SCRIPT) if tokens is None else tokens
        self.healthy = healthy
        self.model_present = model_present
        self.pause_after = pause_after
        self.fail_with = fail_with
        self.delay_s = delay_s
        self.resume = asyncio.Event()
        self.cancelled = False
        self.prompts: list[str] = []

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Record the prompt, then yield the scripted tokens (raising fail_with at the end, if set)."""
        self.prompts.append(prompt)
        try:
            for index, token in enumerate(self.tokens):
                if index == self.pause_after:
                    await self.resume.wait()
                if self.delay_s:
                    await asyncio.sleep(self.delay_s)
                yield token
        except (asyncio.CancelledError, GeneratorExit):
            self.cancelled = True
            raise
        if self.fail_with:
            raise self.fail_with

    async def status(self) -> tuple[bool, bool]:
        """(healthy, healthy and model_present)."""
        return self.healthy, self.healthy and self.model_present

    async def health(self) -> bool:
        """True when reachable and the model is present."""
        return all(await self.status())


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


def ndjson(*objs: dict[str, Any]) -> bytes:
    """Ollama-style NDJSON body: one JSON object per line."""
    return b"".join(json.dumps(o).encode() + b"\n" for o in objs)


class ChunkedStream(httpx.AsyncByteStream):
    """Response body delivered in arbitrary byte pieces; records whether it was closed."""

    def __init__(self, pieces: list[bytes], fail: Exception | None = None) -> None:
        self.pieces = pieces
        self.fail = fail
        self.closed = False
        self.sent = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for piece in self.pieces:
            self.sent += 1
            yield piece
            await asyncio.sleep(0)
        if self.fail:
            raise self.fail

    async def aclose(self) -> None:
        self.closed = True
