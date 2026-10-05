"""Untrusted-input hygiene: the user question is data, never instructions (CLAUDE.md engineering rules)."""

import math
import re
import time
import unicodedata
from collections.abc import Callable

_NEUTRALISE = (
    (re.compile(r"\[\s*chunk", re.IGNORECASE), "(chunk"),
    (re.compile(r"\b(system|context|user question|assistant)\s*:", re.IGNORECASE), r"\1 -"),
    (re.compile(r"<\s*/?\s*question\s*>", re.IGNORECASE), " "),
    (re.compile(r"\[\s*/?\s*inst\s*\]", re.IGNORECASE), " "),
    (re.compile(r"<\s*/?\s*s\s*>", re.IGNORECASE), " "),
)


def strip_invisible(text: str) -> str:
    """Drop control (Cc) and format (Cf) characters; whitespace controls become spaces."""
    return "".join(
        " " if ch in "\t\n\r" else ch for ch in text if ch in "\t\n\r" or unicodedata.category(ch) not in ("Cc", "Cf")
    )


def strip_invisible_block(text: str) -> str:
    """Multi-line text: CRLF/CR become LF; other control (Cc) and format (Cf) characters dropped; tabs become spaces."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch) not in ("Cc", "Cf"))


def clean_question(question: str, max_chars: int) -> str:
    """Strip control characters, neutralise prompt/role markers, collapse whitespace and cap the length."""
    text = strip_invisible(question)
    for pattern, replacement in _NEUTRALISE:
        text = pattern.sub(replacement, text)
    return " ".join(text.split())[:max_chars]


def clean_comment(comment: str, max_chars: int) -> str:
    """Feedback comment: control characters stripped, whitespace collapsed, length capped (never fed to the LLM)."""
    return " ".join(strip_invisible(comment).split())[:max_chars]


class RateLimiter:
    """Per-key token bucket holding per_min requests, refilled continuously (in memory, one process)."""

    def __init__(self, per_min: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._capacity = float(per_min)
        self._rate = per_min / 60.0
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}

    def _level(self, key: str, now: float) -> float:
        """Tokens available to key at time now."""
        tokens, last = self._buckets.get(key, (self._capacity, now))
        return min(self._capacity, tokens + (now - last) * self._rate)

    def allow(self, key: str) -> bool:
        """Take one token for key; False when the bucket is empty."""
        now = self._clock()
        tokens = self._level(key, now)
        allowed = tokens >= 1.0
        self._buckets[key] = (tokens - 1.0 if allowed else tokens, now)
        return allowed

    def retry_after(self, key: str) -> int:
        """Whole seconds until key has a token again (0 if it has one now)."""
        missing = 1.0 - self._level(key, self._clock())
        return max(1, math.ceil(missing / self._rate)) if missing > 0 else 0

    def prune(self) -> None:
        """Forget keys whose bucket has refilled completely (they behave exactly like new keys)."""
        now = self._clock()
        self._buckets = {k: v for k, v in self._buckets.items() if self._level(k, now) < self._capacity}

    @property
    def tracked(self) -> int:
        """Number of keys currently remembered."""
        return len(self._buckets)
