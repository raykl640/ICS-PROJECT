"""Explicit legal references in a question: Act mentions (title, alias, "Cap N") and section/article numbers."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from backend.app.config import ActSpec

_SECTION = re.compile(r"\b(?:sections?|sec\.?|s\.)\s*(\d+[a-z]?)\b")
_ARTICLE = re.compile(r"\b(?:articles?|art\.)\s*(\d+[a-z]?)\b")
_CAP = re.compile(r"\bcap\.?\s*(\d+[a-z]?)\b")


@dataclass(frozen=True)
class Ref:
    """A section or article number, bound to an Act slug when the question names one."""

    unit: Literal["section", "article"]
    num: str
    act: str | None


@dataclass(frozen=True)
class _Span:
    act: str
    start: int
    end: int


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Whole-word pattern for a name, tolerant of punctuation/spacing between its words."""
    words = re.findall(r"\w+", phrase.lower())
    return re.compile(r"\b" + r"\W+".join(map(re.escape, words)) + r"\b")


class RefExtractor:
    """Finds Act mentions and section/article references; sections bind to the nearest mentioned Act."""

    def __init__(self, acts: Sequence[ActSpec], aliases: Mapping[str, Sequence[str]]) -> None:
        self._names = [
            (spec.slug, _phrase_pattern(name)) for spec in acts for name in [spec.name, *aliases.get(spec.slug, [])]
        ]
        self._caps = {spec.cap.lower(): spec.slug for spec in acts if spec.cap}
        self._article_act = next((spec.slug for spec in acts if spec.unit == "Article"), None)
        self._section_acts = {spec.slug for spec in acts if spec.unit == "Section"}

    def _spans(self, text: str) -> list[_Span]:
        """Every Act mention in lower-cased text, in order of position."""
        spans = [_Span(slug, m.start(), m.end()) for slug, pattern in self._names for m in pattern.finditer(text)]
        spans += [
            _Span(self._caps[m.group(1)], m.start(), m.end()) for m in _CAP.finditer(text) if m.group(1) in self._caps
        ]
        return sorted(spans, key=lambda s: s.start)

    def act_mentions(self, query: str) -> list[str]:
        """Slugs of the Acts named in the question, in order of first mention."""
        return list(dict.fromkeys(span.act for span in self._spans(query.lower())))

    def extract_refs(self, query: str) -> list[Ref]:
        """Section/article references in order, deduplicated; articles belong to the Constitution."""
        text = query.lower()
        section_spans = [s for s in self._spans(text) if s.act in self._section_acts]
        found: list[tuple[int, Ref]] = [
            (m.start(), Ref("section", m.group(1), _nearest(section_spans, m.start(), m.end())))
            for m in _SECTION.finditer(text)
        ]
        found += [(m.start(), Ref("article", m.group(1), self._article_act)) for m in _ARTICLE.finditer(text)]
        return list(dict.fromkeys(ref for _, ref in sorted(found, key=lambda pair: pair[0])))


def _nearest(spans: Sequence[_Span], start: int, end: int) -> str | None:
    """Act whose mention is closest to the reference at [start, end), or None if no Act is named."""
    if not spans:
        return None
    return min(spans, key=lambda s: max(s.start - end, start - s.end, 0)).act
