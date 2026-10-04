"""Whoosh BM25F index over chunk titles, text and section numbers, with a query sanitiser."""

import re
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

from whoosh import index as whoosh_index
from whoosh.analysis import IDTokenizer, LowercaseFilter, StemmingAnalyzer
from whoosh.fields import ID, KEYWORD, TEXT, Schema
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.query import Or, Term
from whoosh.scoring import BM25F

from backend.app.models import LegalChunk
from backend.app.retrieval.meta import IndexMeta, now_utc, read_meta, reset_dir, write_meta

QUERY_FIELDS = ["section_title", "text", "section_num"]
_NOT_WORD = re.compile(r"[^\w\s]|_")
# Documents matching more of the query's terms get a bonus over ones that repeat a single term.
_OR_GROUP = OrGroup.factory(0.9)


def _schema() -> Schema:
    """Title is boosted x2 over body; both stemmed. section_num is an exact lower-cased id."""
    return Schema(
        chunk_id=ID(stored=True, unique=True),
        act=KEYWORD(lowercase=True),
        act_slug=KEYWORD,
        section_num=ID(analyzer=IDTokenizer() | LowercaseFilter()),
        section_title=TEXT(analyzer=StemmingAnalyzer(), field_boost=2.0),
        text=TEXT(analyzer=StemmingAnalyzer()),
    )


def sanitize(query: str) -> str:
    """Lower-case and keep only word characters, so no Whoosh syntax survives.

    Removes field prefixes, wildcards, quotes, brackets, boosts and fuzzy marks; lower-casing turns AND/OR/NOT into
    plain words (the analyzer drops them as stopwords).
    """
    return " ".join(_NOT_WORD.sub(" ", query).lower().split())


class SparseIndex:
    """BM25F keyword index; one document per non-repealed chunk."""

    def __init__(self, index: Any, directory: Path, meta: IndexMeta) -> None:
        self._index = index
        self.directory = directory
        self.meta = meta
        self._parser = MultifieldParser(QUERY_FIELDS, index.schema, group=_OR_GROUP)

    @classmethod
    def build(cls, chunks: Sequence[LegalChunk], directory: Path, *, corpus_hash: str) -> "SparseIndex":
        """Replace directory with a fresh index of chunks (caller passes non-repealed chunks only)."""
        reset_dir(directory)
        index = whoosh_index.create_in(str(directory), _schema())
        writer = index.writer()
        for chunk in chunks:
            writer.add_document(
                chunk_id=chunk.chunk_id,
                act=chunk.act,
                act_slug=chunk.act_slug,
                section_num=chunk.section_num,
                section_title=chunk.section_title,
                text=chunk.text,
            )
        writer.commit()
        meta = IndexMeta(
            kind="sparse", corpus_hash=corpus_hash, chunks=len(chunks), entries=index.doc_count(), built_at=now_utc()
        )
        write_meta(directory, meta)
        return cls(index, directory, meta)

    @classmethod
    def open(cls, directory: Path, *, corpus_hash: str) -> "SparseIndex":
        """Open a built index; IndexMismatchError if missing or built from another corpus."""
        meta = read_meta(directory, "sparse", corpus_hash)
        return cls(whoosh_index.open_dir(str(directory)), directory, meta)

    @property
    def doc_count(self) -> int:
        """Number of indexed chunks."""
        return int(self._index.doc_count())

    def search(self, query: str, k: int, acts: Collection[str] | None = None) -> list[tuple[str, float]]:
        """Top-k (chunk_id, BM25F score), descending; acts restricts to those act_slugs (empty/None = all)."""
        cleaned = sanitize(query)
        if not cleaned:
            return []
        parsed = self._parser.parse(cleaned)
        act_filter = Or([Term("act_slug", act) for act in sorted(acts)]) if acts else None
        with self._index.searcher(weighting=BM25F()) as searcher:
            hits = searcher.search(parsed, limit=k, filter=act_filter)
            return [(hit["chunk_id"], float(hit.score)) for hit in hits]
