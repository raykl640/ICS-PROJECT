"""Retrieval ground truth: schema, loading, and resolution of each (act, section) to a chunk in the store.

The answer key is written by a human (eval/ground_truth.json); nothing here generates or suggests relevant sections.
"""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator

from backend.app.config import ActSpec, Settings, get_settings
from backend.app.models import UserLanguage
from backend.app.retrieval.store import ChunkStore

_UNIT_PREFIX = re.compile(r"^(?:sections?|s\.|sec\.?|articles?|art\.?)\s*", re.IGNORECASE)


class RelevantRef(BaseModel):
    """One correct provision: Act (name or slug) and section/article number (or schedule, e.g. "First Schedule")."""

    act: str = Field(min_length=1)
    section: str = Field(min_length=1)

    @field_validator("section", mode="before")
    @classmethod
    def _number_as_text(cls, value: Any) -> Any:
        """Accept 41 as well as "41"."""
        return str(value) if isinstance(value, int) else value


class GroundTruthEntry(BaseModel):
    """One retrieval query with the provisions a correct answer must draw on."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    lang: UserLanguage
    category: str = Field(min_length=1)
    relevant: list[RelevantRef] = Field(min_length=1)

    @field_validator("question", "category", "id", mode="after")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Reject whitespace-only text."""
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


GROUND_TRUTH = TypeAdapter(list[GroundTruthEntry])


@dataclass(frozen=True)
class ResolvedEntry:
    """A ground-truth entry with its relevant provisions as chunk ids."""

    entry: GroundTruthEntry
    relevant_ids: frozenset[str]


@dataclass(frozen=True)
class Validation:
    """Resolved entries (only when there are no problems) and every problem found."""

    entries: list[ResolvedEntry]
    problems: list[str]

    @property
    def ok(self) -> bool:
        """True when the file can be used for evaluation."""
        return not self.problems


def _act_lookup(acts: Sequence[ActSpec]) -> dict[str, str]:
    """Lower-cased Act name or slug -> slug."""
    return {key: act.slug for act in acts for key in (act.slug, act.name.lower())}


def _section_index(store: ChunkStore) -> dict[tuple[str, str], list[str]]:
    """(act slug, lower-cased section_num) -> chunk ids, in document order."""
    index: dict[tuple[str, str], list[str]] = {}
    for chunk in store.all():
        index.setdefault((chunk.act_slug, chunk.section_num.lower()), []).append(chunk.chunk_id)
    return index


class RefResolver:
    """Maps (act, section) as a human writes it to exactly one chunk id, or explains why it cannot."""

    def __init__(self, store: ChunkStore, acts: Sequence[ActSpec]) -> None:
        self._store = store
        self._acts = _act_lookup(acts)
        self._sections = _section_index(store)

    def resolve(self, ref: RelevantRef) -> tuple[str | None, str | None]:
        """(chunk_id, None) or (None, problem). An exact id suffix ("41a", "sch1", "5-2") wins over section_num."""
        slug = self._acts.get(ref.act.strip().lower())
        if slug is None:
            return None, f"unknown act {ref.act!r}"
        key = _UNIT_PREFIX.sub("", ref.section.strip()).lower()
        exact = f"{slug}-{key.replace(' ', '-')}"
        matches = [exact] if exact in self._store else self._sections.get((slug, key), [])
        if not matches:
            return None, f"{ref.act} {ref.section!r} is not in the chunk store"
        if len(matches) > 1:
            return None, f"{ref.act} {ref.section!r} is ambiguous ({', '.join(matches)}); give the chunk id suffix"
        chunk = self._store.get(matches)[0]
        if chunk.repealed:
            return None, f"{ref.act} {ref.section!r} ({chunk.chunk_id}) is repealed and not indexed"
        return chunk.chunk_id, None


def _schema_problems(err: ValidationError) -> list[str]:
    """One line per pydantic error: entry index, field path, message."""
    return [
        f"entry {'.'.join(str(p) for p in e['loc']) or '(file)'}: {e['msg']}" for e in err.errors(include_url=False)
    ]


def validate_ground_truth(raw: Any, store: ChunkStore, acts: Sequence[ActSpec]) -> Validation:
    """Check structure, unique ids and questions, and that every relevant provision resolves to one indexed chunk."""
    try:
        entries = GROUND_TRUTH.validate_python(raw)
    except ValidationError as err:
        return Validation([], _schema_problems(err))
    problems: list[str] = []
    if not entries:
        problems.append("no entries")
    for field in ("id", "question"):
        values = [getattr(e, field).lower() for e in entries]
        problems += [f"duplicate {field} {v!r}" for v in sorted({v for v in values if values.count(v) > 1})]
    resolver = RefResolver(store, acts)
    resolved = []
    for entry in entries:
        ids = set()
        for ref in entry.relevant:
            chunk_id, problem = resolver.resolve(ref)
            if problem:
                problems.append(f"{entry.id}: {problem}")
            else:
                ids.add(str(chunk_id))
        resolved.append(ResolvedEntry(entry, frozenset(ids)))
    return Validation(resolved if not problems else [], problems)


def load_ground_truth(path: Path, store: ChunkStore, acts: Sequence[ActSpec]) -> Validation:
    """Validate a ground-truth file; a missing or non-JSON file is reported as a problem, not raised."""
    if not path.exists():
        return Validation([], [f"{path} does not exist; copy eval/ground_truth.template.json and fill it in"])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        return Validation([], [f"{path}: invalid JSON ({err})"])
    return validate_ground_truth(raw, store, acts)


def json_schema() -> dict[str, Any]:
    """JSON Schema of the ground-truth file (for editors and documentation)."""
    return GROUND_TRUTH.json_schema()


def schema_main(argv: Sequence[str] | None = None) -> int:
    """CLI: print the ground-truth JSON Schema."""
    argparse.ArgumentParser(description="Print the JSON Schema of eval/ground_truth.json.").parse_args(argv)
    print(json.dumps(json_schema(), indent=2))
    return 0


def validate_main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI: exit 0 when the ground truth is valid, 1 with one line per problem otherwise (2: chunk store missing)."""
    parser = argparse.ArgumentParser(description="Validate eval/ground_truth.json against the chunk store.")
    parser.add_argument("path", nargs="?", type=Path, help="ground-truth file (default: eval/ground_truth.json)")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    try:
        store = ChunkStore.load(settings.chunks_path)
    except FileNotFoundError:
        print(f"{settings.chunks_path} is missing; run python -m backend.app.ingestion.build_index", file=sys.stderr)
        return 2
    path = args.path or settings.ground_truth_path
    result = load_ground_truth(path, store, settings.acts)
    if not result.ok:
        print(f"{path}: {len(result.problems)} problem(s)", file=sys.stderr)
        for problem in result.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    refs = sum(len(r.relevant_ids) for r in result.entries)
    categories = sorted({r.entry.category for r in result.entries})
    print(f"OK: {len(result.entries)} queries, {refs} relevant chunks, categories: {', '.join(categories)}")
    return 0
