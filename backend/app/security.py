"""Untrusted-input hygiene: the user question is data, never instructions (CLAUDE.md engineering rules)."""

import re
import unicodedata

_NEUTRALISE = (
    (re.compile(r"\[\s*chunk", re.IGNORECASE), "(chunk"),
    (re.compile(r"\b(system|context|user question|assistant)\s*:", re.IGNORECASE), r"\1 -"),
    (re.compile(r"<\s*/?\s*question\s*>", re.IGNORECASE), " "),
    (re.compile(r"\[\s*/?\s*inst\s*\]", re.IGNORECASE), " "),
    (re.compile(r"<\s*/?\s*s\s*>", re.IGNORECASE), " "),
)


def _strip_invisible(text: str) -> str:
    """Drop control (Cc) and format (Cf) characters; whitespace controls become spaces."""
    return "".join(
        " " if ch in "\t\n\r" else ch for ch in text if ch in "\t\n\r" or unicodedata.category(ch) not in ("Cc", "Cf")
    )


def clean_question(question: str, max_chars: int) -> str:
    """Strip control characters, neutralise prompt/role markers, collapse whitespace and cap the length."""
    text = _strip_invisible(question)
    for pattern, replacement in _NEUTRALISE:
        text = pattern.sub(replacement, text)
    return " ".join(text.split())[:max_chars]
