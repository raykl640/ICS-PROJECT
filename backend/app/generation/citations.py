"""Extract (Act, section/article) citations from an answer and check them against the chunks the model was given."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from backend.app.config import get_settings
from backend.app.models import CitationCheck, LegalChunk
from backend.app.retrieval.refs import ActSpan, RefExtractor
from backend.app.retrieval.router import Router

Unit = Literal["section", "article"]

_NUM = r"\d+[a-z]?(?:\s*\(\w{1,4}\))*"
_DASH = "-\u2013\u2014"  # hyphen, en dash, em dash
_SEP = rf"\s*(?:,|&|\band\b|\bor\b|\bto\b|[{_DASH}])\s*"
_CITE = re.compile(rf"\b(?P<kw>sections?|ss\.|s\.|secs?\.?|articles?|arts?\.)\s*(?P<nums>{_NUM}(?:{_SEP}{_NUM})*)")
_NUM_OR_RANGE = re.compile(rf"(?P<num>\d+[a-z]?)(?:\s*\(\w{{1,4}}\))*|(?P<range>\bto\b|[{_DASH}])")
_OF_THE = re.compile(r"\s*of\s+(?:the\s+)?")
_BIND_CHARS = 60
_MAX_RANGE = 20


@dataclass(frozen=True)
class Citation:
    """One cited provision; act is an Act slug, or None when no Act is named near it."""

    unit: Unit
    num: str
    act: str | None


def _numbers(nums: str) -> list[str]:
    """Section numbers in a list such as "41(2), 43 and 45" or a range "41 to 43" (subsections dropped)."""
    out: list[str] = []
    pending_range = False
    for m in _NUM_OR_RANGE.finditer(nums):
        if m["range"]:
            pending_range = bool(out)
            continue
        num = m["num"]
        if pending_range and out[-1].isdigit() and num.isdigit() and 0 < int(num) - int(out[-1]) <= _MAX_RANGE:
            out += [str(n) for n in range(int(out[-1]) + 1, int(num) + 1)]
        else:
            out.append(num)
        pending_range = False
    return out


def _bind(spans: Sequence[ActSpan], text: str, start: int, end: int) -> str | None:
    """Act for a citation at [start, end): "... of the <Act>" first, else the nearest Act mention close by."""
    of_the = _OF_THE.match(text, end)
    if of_the:
        following = [s for s in spans if s.start == of_the.end()]
        if following:
            return following[0].act
    before = [s for s in spans if s.end <= start and start - s.end <= _BIND_CHARS]
    if before:
        return before[-1].act
    after = [s for s in spans if s.start >= end and s.start - end <= _BIND_CHARS]
    return after[0].act if after else None


def extract_citations(text: str, refs: RefExtractor | None = None) -> list[Citation]:
    """Citations in order of appearance, deduplicated; articles belong to the Constitution, sections to a named Act."""
    refs = refs or default_refs()
    lowered = text.lower()
    spans = refs.act_spans(lowered)
    section_spans = [s for s in spans if s.act in refs.section_acts]
    found: list[Citation] = []
    for m in _CITE.finditer(lowered):
        if m["kw"].startswith("art"):
            unit: Unit = "article"
            act = refs.article_act
        else:
            unit = "section"
            act = _bind(section_spans, lowered, m.start(), m.end())
        found += [Citation(unit, num, act) for num in _numbers(m["nums"])]
    return list(dict.fromkeys(found))


def _label(citation: Citation, names: dict[str, str]) -> str:
    """Human-readable citation, e.g. "Employment Act s. 41" or "Constitution of Kenya Article 41"."""
    unit = "Article " if citation.unit == "article" else "s. "
    act = names.get(citation.act, citation.act) if citation.act else "(no Act named)"
    return f"{act} {unit}{citation.num}"


def check_citations(text: str, chunks: Sequence[LegalChunk], refs: RefExtractor | None = None) -> CitationCheck:
    """Split the answer's citations into those matching a given chunk and the rest (possible hallucinations)."""
    refs = refs or default_refs()
    names = {**refs.names, **{c.act_slug: c.act for c in chunks}}
    keys = {(c.act_slug, c.unit_type, c.section_num.lower()) for c in chunks}
    check = CitationCheck()
    for citation in extract_citations(text, refs):
        if citation.act:
            ok = (citation.act, citation.unit, citation.num) in keys
        else:
            ok = any((unit, num) == (citation.unit, citation.num) for _, unit, num in keys)
        (check.verified if ok else check.unmatched).append(_label(citation, names))
    return check


@lru_cache(maxsize=1)
def default_refs() -> RefExtractor:
    """Act names, aliases (domains.yaml) and Cap numbers of the configured corpus."""
    return Router.from_settings(get_settings()).refs
