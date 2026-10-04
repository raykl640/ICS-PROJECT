"""Keyword domain router (ARCHITECTURE.md §5.2): question -> ordered Act slugs, or None for the full corpus."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from whoosh.lang.porter import stem

from backend.app.config import ActSpec, Settings
from backend.app.retrieval.refs import RefExtractor

Phrase = tuple[str, ...]


def stem_words(text: str) -> list[str]:
    """Lower-cased, Porter-stemmed words of text (the router's light stemming)."""
    return [str(stem(word)) for word in re.findall(r"\w+", text.lower())]


@dataclass(frozen=True)
class DomainTable:
    """Stemmed keyword phrases and explicit aliases per Act, plus the rights co-domain rule."""

    terms: Mapping[str, frozenset[Phrase]]
    aliases: Mapping[str, Sequence[str]]
    co_domain: str
    co_domain_for: frozenset[str]

    @classmethod
    def build(cls, data: Mapping[str, Any], acts: Sequence[ActSpec]) -> "DomainTable":
        """Validate raw table data against the corpus Acts and stem every term."""
        known = {spec.slug for spec in acts}
        unknown = ({data["co_domain"], *data["co_domain_for"], *data["acts"]}) - known
        if unknown:
            raise ValueError(f"domains table names unknown Acts: {sorted(unknown)}")
        return cls(
            terms={
                slug: frozenset(tuple(stem_words(t)) for t in entry["terms"]) for slug, entry in data["acts"].items()
            },
            aliases={slug: list(entry["aliases"]) for slug, entry in data["acts"].items()},
            co_domain=data["co_domain"],
            co_domain_for=frozenset(data["co_domain_for"]),
        )


def load_domains(path: Path, acts: Sequence[ActSpec]) -> DomainTable:
    """Read domains.yaml."""
    return DomainTable.build(yaml.safe_load(path.read_text(encoding="utf-8")), acts)


def _contains(words: Sequence[str], phrase: Phrase) -> bool:
    """True if phrase occurs as contiguous words."""
    n = len(phrase)
    return any(tuple(words[i : i + n]) == phrase for i in range(len(words) - n + 1))


class Router:
    """Explicit Act/Article mentions win; otherwise Acts ordered by matched-term count, Constitution as co-domain."""

    def __init__(self, table: DomainTable, refs: RefExtractor) -> None:
        self.table = table
        self.refs = refs
        self._order = {slug: i for i, slug in enumerate(table.terms)}

    @classmethod
    def from_settings(cls, settings: Settings) -> "Router":
        """Router over the configured Acts and domains.yaml."""
        table = load_domains(settings.domains_path, settings.acts)
        return cls(table, RefExtractor(settings.acts, table.aliases))

    def route(self, question: str) -> list[str] | None:
        """Ordered Act slugs for the question, or None when nothing matches (search the full corpus)."""
        explicit = self._explicit(question)
        if explicit:
            return explicit
        words = stem_words(question)
        scores = {slug: sum(_contains(words, p) for p in phrases) for slug, phrases in self.table.terms.items()}
        acts = sorted((s for s, n in scores.items() if n), key=lambda s: (-scores[s], self._order[s]))
        if self.table.co_domain not in acts and self.table.co_domain_for & set(acts):
            acts.append(self.table.co_domain)
        return acts or None

    def _explicit(self, question: str) -> list[str]:
        """Acts named outright or implied by an Article reference, in order of mention."""
        mentioned = self.refs.act_mentions(question)
        articles = [ref.act for ref in self.refs.extract_refs(question) if ref.unit == "article" and ref.act]
        return list(dict.fromkeys([*mentioned, *articles]))
