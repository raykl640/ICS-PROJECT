"""Cross-references between corpus sections, computed at index build into refs.json (DESIGN_V2 "API v2" Laws).

A reference resolves to a chunk id only when the target exists, is in the same Act (or the Act the text names) with the
same unit type, and is not repealed. "section N" in a Constitution chunk names no Section-unit Act, so it never resolves
to Article N; "section N of the <unknown> Act" stays an unlinked label.
"""

import re
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ValidationError

from backend.app.models import LegalChunk
from backend.app.retrieval.meta import REBUILD_COMMAND, IndexMismatchError
from backend.app.retrieval.refs import ActSpan, RefExtractor
from backend.app.retrieval.store import ChunkStore

_SECTION = re.compile(r"\b(?:sections?|sec\.|s\.)\s*(\d+[a-z]?)\b")
_ARTICLE = re.compile(r"\barticles?\s*(\d+[a-z]?)\b")
# "(2)(a) of the ", " of this " after a reference: the Act it belongs to follows.
_OF = re.compile(r"(?:\s*\(\w{1,4}\))*\s+of\s+(the|this)\s+")
_THIS_ACT = re.compile(r"act\b")
# Act named by the text but not in the corpus.
_FOREIGN = "-"


class RefLink(BaseModel):
    """A reference shown in the reader: its label and, when resolved, the target chunk id."""

    label: str
    chunk_id: str | None = None


class CrossRefs(BaseModel):
    """Outgoing references per chunk and the inverse "cited by" lists, tied to the corpus they were built from."""

    corpus_hash: str
    out: dict[str, list[RefLink]]
    cited_by: dict[str, list[str]]

    @property
    def resolved(self) -> int:
        """Number of resolved (linked) references."""
        return sum(link.chunk_id is not None for links in self.out.values() for link in links)

    @property
    def unresolved(self) -> int:
        """Number of references shown as plain labels."""
        return sum(link.chunk_id is None for links in self.out.values() for link in links)


def _bound_act(text: str, end: int, spans: list[ActSpan], default: str | None) -> str | None:
    """Act a reference ending at end belongs to: an "of the X" that follows it, else default ("-" = not in corpus)."""
    tail = _OF.match(text, end)
    if tail is None or tail.group(1) == "this":
        return default
    named = next((span.act for span in spans if span.start == tail.end()), None)
    if named is not None:
        return named
    return default if _THIS_ACT.match(text, tail.end()) else _FOREIGN


def _raw_refs(chunk: LegalChunk, extractor: RefExtractor) -> Iterator[tuple[int, str, str, str]]:
    """(position, unit, number, act slug) for every reference to a corpus Act of the right unit type.

    References to laws outside the corpus, and bare "section N" in the Constitution, are left out."""
    text = chunk.text.lower()
    spans = extractor.act_spans(text)
    own_section_act = chunk.act_slug if chunk.act_slug in extractor.section_acts else None
    for m in _SECTION.finditer(text):
        act = _bound_act(text, m.end(), spans, own_section_act)
        if act in extractor.section_acts:
            yield m.start(), "section", m.group(1), act
    for m in _ARTICLE.finditer(text):
        act = _bound_act(text, m.end(), spans, extractor.article_act)
        if act is not None and act == extractor.article_act:
            yield m.start(), "article", m.group(1), act


def _label(unit: str, num: str, act: str, chunk: LegalChunk, extractor: RefExtractor) -> str:
    """ "Section 41" within the same Act, "Employment Act, section 41" across Acts."""
    if act == chunk.act_slug:
        return f"{unit.capitalize()} {num}"
    return f"{extractor.names[act]}, {unit} {num}"


def build_cross_refs(store: ChunkStore, extractor: RefExtractor) -> CrossRefs:
    """Outgoing references of every non-repealed chunk (in text order, deduplicated) and the inverse lists."""
    targets: dict[tuple[str, str, str], str] = {}
    for chunk in store.indexable():
        targets.setdefault((chunk.act_slug, chunk.unit_type, chunk.section_num.lower()), chunk.chunk_id)
    order = {chunk.chunk_id: n for n, chunk in enumerate(store.all())}
    out: dict[str, list[RefLink]] = {}
    cited_by: dict[str, set[str]] = {}
    for chunk in store.indexable():
        links: dict[str, RefLink] = {}
        for _, unit, num, act in sorted(_raw_refs(chunk, extractor), key=lambda ref: ref[0]):
            target = targets.get((act, unit, num))
            if target == chunk.chunk_id:
                continue
            label = _label(unit, num, act, chunk, extractor)
            links.setdefault(label, RefLink(label=label, chunk_id=target))
            if target is not None:
                cited_by.setdefault(target, set()).add(chunk.chunk_id)
        if links:
            out[chunk.chunk_id] = list(links.values())
    inverse = {target: sorted(sources, key=order.__getitem__) for target, sources in cited_by.items()}
    return CrossRefs(corpus_hash=store.corpus_hash, out=out, cited_by=inverse)


def save_cross_refs(refs: CrossRefs, path: Path) -> None:
    """Write refs.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(refs.model_dump_json() + "\n", encoding="utf-8")


def load_cross_refs(path: Path, corpus_hash: str) -> CrossRefs:
    """Read refs.json; IndexMismatchError when it is missing, unreadable or built from another corpus."""
    try:
        refs = CrossRefs.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as err:
        raise IndexMismatchError(f"no readable cross-references at {path}; build them with: {REBUILD_COMMAND}") from err
    if refs.corpus_hash != corpus_hash:
        raise IndexMismatchError(f"cross-references at {path} are stale; rebuild: {REBUILD_COMMAND}")
    return refs
