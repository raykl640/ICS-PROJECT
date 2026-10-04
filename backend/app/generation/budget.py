"""Token estimates and chunk fitting for the LLM context budget (no tokenizer download needed)."""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

TRUNCATION_MARKER = "[... truncated — see Sources]"

# Words and punctuation marks each count: statute text is dense with "41(2)(a)"-style references that tokenise long.
_UNIT = re.compile(r"\w+|[^\w\s]")
_SENTENCE_END = re.compile(r"[.;:](?=\s)")
_SENTENCE_MIN_KEEP = 0.7


def est_tokens(text: str, per_word: float) -> int:
    """Conservative token estimate: (words + punctuation marks) * per_word, rounded up."""
    return math.ceil(per_word * len(_UNIT.findall(text)))


def truncate_text(text: str, max_tokens: int, per_word: float) -> str:
    """Cut text at a word (preferably sentence) boundary so text + marker fits max_tokens; append the marker."""
    keep = max(0, math.floor(max_tokens / per_word) - len(_UNIT.findall(TRUNCATION_MARKER)))
    units = list(_UNIT.finditer(text))
    head = text[: units[keep - 1].end()] if keep else ""
    ends = [m.end() for m in _SENTENCE_END.finditer(head + " ")]
    if ends and ends[-1] >= _SENTENCE_MIN_KEEP * len(head):
        head = head[: ends[-1]]
    return f"{head.rstrip()}\n{TRUNCATION_MARKER}".lstrip()


@dataclass(frozen=True)
class FitLimits:
    """Token limits for fitting chunk bodies into the context."""

    available: int
    per_chunk: int
    min_chunk: int
    per_word: float


@dataclass(frozen=True)
class Fitted:
    """A chunk body as it goes into the prompt; body is None when the chunk was dropped for lack of space."""

    body: str | None
    truncated: bool


def fit_bodies(items: Sequence[tuple[int, str]], limits: FitLimits) -> list[Fitted]:
    """Fit (header_tokens, body) pairs in rank order: higher ranks keep their text, lower ranks are truncated first."""
    left = limits.available
    fitted: list[Fitted] = []
    for header_tokens, body in items:
        need = est_tokens(body, limits.per_word)
        allowance = min(limits.per_chunk, left - header_tokens)
        if need <= allowance:
            fitted.append(Fitted(body, truncated=False))
            left -= header_tokens + need
        elif allowance >= limits.min_chunk:
            cut = truncate_text(body, allowance, limits.per_word)
            fitted.append(Fitted(cut, truncated=True))
            left -= header_tokens + est_tokens(cut, limits.per_word)
        else:
            fitted.append(Fitted(None, truncated=True))
    return fitted
