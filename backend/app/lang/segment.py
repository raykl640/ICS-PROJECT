"""Split text into translation-sized pieces by line, then sentence, then words; separators are kept verbatim."""

import math
import re
from dataclasses import dataclass

from backend.app.generation.budget import est_tokens

_LINE_BREAK = re.compile(r"(\n\s*)")
# Leading list markers ("1. ", "- ") stay out of the model input so they come back unchanged.
_LINE_PREFIX = re.compile(r"^(?:[-*•]\s+|\d{1,3}[.)]\s+)")
# A sentence ends at . ! or ? followed by space and a capital or opening mark ("s. 41" and "Cap. 226" do not split).
_SENTENCE_GAP = re.compile(r"(?<=[.!?])(\s+)(?=[\"'(\[]?[A-Z])")
_WORD_GAP = re.compile(r"(\s+)")


@dataclass(frozen=True)
class Part:
    """A piece of text; only parts with translate=True go to the model. "".join of all parts is the input."""

    text: str
    translate: bool


def segment(text: str, max_tokens: int, per_word: float, pack: bool = True) -> list[Part]:
    """Split text into parts whose translatable pieces each fit max_tokens; pack=False keeps one sentence per part."""
    parts: list[Part] = []
    for piece in _LINE_BREAK.split(text):
        body = piece.strip()
        if not body:
            parts.append(Part(piece, False))
            continue
        start = piece.index(body)
        prefix_len = start + len(body) - len(_LINE_PREFIX.sub("", body, count=1))
        parts.append(Part(piece[:prefix_len], False))
        parts += _pack(_SENTENCE_GAP.split(piece[prefix_len : start + len(body)]), max_tokens, per_word, pack)
        parts.append(Part(piece[start + len(body) :], False))
    return [p for p in parts if p.text]


def _pack(pieces: list[str], max_tokens: int, per_word: float, pack: bool) -> list[Part]:
    """Join [sentence, gap, sentence, ...] greedily into groups under max_tokens; gaps between groups stay as is."""
    parts: list[Part] = []
    group, group_gap = "", ""
    for sentence, gap in zip(pieces[0::2], [*pieces[1::2], ""], strict=True):
        too_long = est_tokens(sentence, per_word) > max_tokens
        if group and (not pack or too_long or est_tokens(group + group_gap + sentence, per_word) > max_tokens):
            parts += [Part(group, True), Part(group_gap, False)]
            group = ""
        if too_long:
            parts += [*_split_words(sentence, max_tokens, per_word), Part(gap, False)]
            continue
        group = group + group_gap + sentence if group else sentence
        group_gap = gap
    if group:
        parts += [Part(group, True), Part(group_gap, False)]
    return parts


def _split_words(sentence: str, max_tokens: int, per_word: float) -> list[Part]:
    """Cut an over-long sentence into runs of whole words that each fit max_tokens."""
    words = _WORD_GAP.split(sentence)
    per_run = max(1, math.floor(max_tokens / per_word / 2))  # punctuation counts too, so stay well under
    parts: list[Part] = []
    for i in range(0, len(words), 2 * per_run):
        run = words[i : i + 2 * per_run]
        gap = run.pop() if len(run) % 2 == 0 else ""
        parts.append(Part("".join(run), True))
        parts.append(Part(gap, False))
    return parts
