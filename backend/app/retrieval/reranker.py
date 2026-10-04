"""Cross-encoder interface. The ms-marco implementation and rerank logic are added in M4."""

import re
from typing import Protocol

_WORD = re.compile(r"\w+")


class CrossEncoderLike(Protocol):
    def score(self, query: str, docs: list[str]) -> list[float]:
        """Return one relevance score per doc; higher is more relevant."""
        ...


class FakeReranker:
    """Scores by count of distinct query words in the doc; 0 means no overlap."""

    def score(self, query: str, docs: list[str]) -> list[float]:
        terms = set(_WORD.findall(query.lower()))
        return [float(len(terms & set(_WORD.findall(d.lower())))) for d in docs]
