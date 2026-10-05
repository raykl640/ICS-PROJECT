"""Laws browser data: Act list, tables of contents, verbatim sections with cross-references, BM25 search snippets.

Statute text is returned exactly as stored in chunks.json. Search marks are [start, end) offsets in Unicode code points
into the snippet string, never HTML.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel
from whoosh.analysis import StemmingAnalyzer

from backend.app.config import ActSpec, Settings
from backend.app.laws.xrefs import CrossRefs, RefLink, load_cross_refs
from backend.app.models import LegalChunk
from backend.app.retrieval.sparse import SparseIndex, sanitize
from backend.app.retrieval.store import ChunkStore

_ELLIPSIS = "…"
# Context kept before the first mark of the chosen window.
_LEAD_FRACTION = 4


class ActInfo(BaseModel):
    """One Act in the browser list."""

    slug: str
    name: str
    year: int
    unit: str
    sections: int
    repealed: int


class TocItem(BaseModel):
    """One section, article or schedule in a table of contents."""

    chunk_id: str
    num: str
    title: str
    unit_type: str
    repealed: bool


class TocGroup(BaseModel):
    """Consecutive items under the same Chapter/Part heading ("" when the Act has none)."""

    part: str
    items: list[TocItem]


class ActToc(BaseModel):
    """An Act with its table of contents."""

    act: ActInfo
    groups: list[TocGroup]


class SectionView(BaseModel):
    """A section as stored, with its neighbours in the Act and its references both ways."""

    chunk: LegalChunk
    prev: str | None
    next: str | None
    refs_out: list[RefLink]
    refs_in: list[RefLink]


class SearchHit(BaseModel):
    """A BM25 hit with a snippet of the section text and the matched words' offsets in it."""

    chunk_id: str
    act: str
    act_slug: str
    unit_type: str
    num: str
    title: str
    snippet: str
    marks: list[tuple[int, int]]


@dataclass(frozen=True)
class Snippet:
    """A window of a text with mark offsets relative to it."""

    text: str
    marks: list[tuple[int, int]]


def _heading(chunk: LegalChunk) -> str:
    """The TOC group label of a chunk: its Chapter and Part headings."""
    return " — ".join(h for h in (chunk.chapter, chunk.part) if h)


def match_spans(text: str, query: str) -> list[tuple[int, int]]:
    """Offsets of the words in text whose stem matches a stem of the (sanitised) query."""
    analyzer = StemmingAnalyzer()
    stems = {token.text for token in analyzer(sanitize(query))}
    if not stems:
        return []
    return [(t.startchar, t.endchar) for t in analyzer(text, chars=True) if t.text in stems]


def make_snippet(text: str, spans: Sequence[tuple[int, int]], size: int) -> Snippet:
    """The size-character window with the most matches, cut at word boundaries, with "…" where text was cut."""
    best = max((sum(1 for s, e in spans if start <= s and e <= start + size), -start) for start, _ in spans or [(0, 0)])
    first = -best[1]
    start = max(0, min(first - size // _LEAD_FRACTION, len(text) - size))
    end = min(len(text), start + size)
    if start > 0 and " " in text[start:first]:
        start = text.index(" ", start, first) + 1
    if end < len(text) and " " in text[max(start, end - size // _LEAD_FRACTION) : end]:
        end = text.rindex(" ", start, end)
    prefix = _ELLIPSIS if start > 0 else ""
    suffix = _ELLIPSIS if end < len(text) else ""
    shift = len(prefix) - start
    marks = [(s + shift, e + shift) for s, e in spans if start <= s and e <= end]
    return Snippet(prefix + text[start:end] + suffix, marks)


class LawCatalog:
    """Read-only view of the corpus for the laws browser and search."""

    def __init__(
        self, store: ChunkStore, sparse: SparseIndex, refs: CrossRefs, acts: Sequence[ActSpec], snippet_chars: int
    ) -> None:
        self._store = store
        self._sparse = sparse
        self._refs = refs
        self._snippet_chars = snippet_chars
        self._by_act: dict[str, list[LegalChunk]] = {spec.slug: [] for spec in acts}
        for chunk in store.all():
            self._by_act.setdefault(chunk.act_slug, []).append(chunk)
        self._specs = {spec.slug: spec for spec in acts}
        self._position = {c.chunk_id: n for chunks in self._by_act.values() for n, c in enumerate(chunks)}

    def _info(self, spec: ActSpec) -> ActInfo:
        chunks = self._by_act[spec.slug]
        repealed = sum(c.repealed for c in chunks)
        return ActInfo(
            slug=spec.slug,
            name=spec.name,
            year=spec.year,
            unit=spec.unit,
            sections=len(chunks) - repealed,
            repealed=repealed,
        )

    def acts(self) -> list[ActInfo]:
        """Every Act in config order with its in-force and repealed unit counts."""
        return [self._info(spec) for spec in self._specs.values()]

    def toc(self, slug: str) -> ActToc | None:
        """The Act's units in document order, grouped by consecutive Chapter/Part heading; None for an unknown slug."""
        spec = self._specs.get(slug)
        if spec is None:
            return None
        groups: list[TocGroup] = []
        for chunk in self._by_act[slug]:
            if not groups or groups[-1].part != _heading(chunk):
                groups.append(TocGroup(part=_heading(chunk), items=[]))
            groups[-1].items.append(
                TocItem(
                    chunk_id=chunk.chunk_id,
                    num=chunk.section_num,
                    title=chunk.section_title,
                    unit_type=chunk.unit_type,
                    repealed=chunk.repealed,
                )
            )
        return ActToc(act=self._info(spec), groups=groups)

    def _citing(self, chunk_id: str) -> RefLink:
        chunk = self._store.get([chunk_id])[0]
        return RefLink(label=f"{chunk.act}, {chunk.unit_type} {chunk.section_num}", chunk_id=chunk_id)

    def section(self, chunk_id: str) -> SectionView | None:
        """A unit verbatim with prev/next ids in its Act and its references; None for an unknown id."""
        if chunk_id not in self._store:
            return None
        chunk = self._store.get([chunk_id])[0]
        siblings = self._by_act[chunk.act_slug]
        n = self._position[chunk_id]
        return SectionView(
            chunk=chunk,
            prev=siblings[n - 1].chunk_id if n > 0 else None,
            next=siblings[n + 1].chunk_id if n + 1 < len(siblings) else None,
            refs_out=self._refs.out.get(chunk_id, []),
            refs_in=[self._citing(cid) for cid in self._refs.cited_by.get(chunk_id, [])],
        )

    def search(self, query: str, acts: Sequence[str], limit: int) -> list[SearchHit]:
        """BM25 hits (repealed units are not indexed) with snippets around the best cluster of matched words."""
        hits = self._sparse.search(query, limit, acts or None)
        out = []
        for chunk in self._store.get(cid for cid, _ in hits):
            snippet = make_snippet(chunk.text, match_spans(chunk.text, query), self._snippet_chars)
            out.append(
                SearchHit(
                    chunk_id=chunk.chunk_id,
                    act=chunk.act,
                    act_slug=chunk.act_slug,
                    unit_type=chunk.unit_type,
                    num=chunk.section_num,
                    title=chunk.section_title,
                    snippet=snippet.text,
                    marks=snippet.marks,
                )
            )
        return out


def load_catalog(settings: Settings) -> LawCatalog:
    """The catalog over chunks.json, the sparse index and refs.json (IndexMismatchError if any is stale or missing)."""
    store = ChunkStore.load(settings.chunks_path)
    sparse = SparseIndex.open(settings.sparse_index_dir, corpus_hash=store.corpus_hash)
    refs = load_cross_refs(settings.refs_path, store.corpus_hash)
    return LawCatalog(store, sparse, refs, settings.acts, settings.snippet_chars)
