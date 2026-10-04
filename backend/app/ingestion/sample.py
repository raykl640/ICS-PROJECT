"""Reproducible random chunk samples for the M1 human review gate (wrapped by scripts/inspect_chunks.py)."""

import argparse
import json
import random
import sys
from collections.abc import Sequence
from pathlib import Path

from backend.app.config import Settings, get_settings
from backend.app.models import LegalChunk


def load_chunks(path: Path) -> list[LegalChunk]:
    """Chunks from chunks.json in document order."""
    return [LegalChunk.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def select(
    chunks: list[LegalChunk], per_act: int, act: str | None = None, section: str | None = None, seed: int = 0
) -> list[LegalChunk]:
    """Up to per_act random chunks per Act (seeded, kept in document order); a section filter returns all matches."""
    pool = [c for c in chunks if act is None or c.act_slug == act]
    if section is not None:
        return [c for c in pool if c.section_num.lower() == section.lower()]
    rng = random.Random(seed)
    by_act: dict[str, list[int]] = {}
    for index, chunk in enumerate(pool):
        by_act.setdefault(chunk.act_slug, []).append(index)
    picked = [i for indices in by_act.values() for i in rng.sample(indices, min(per_act, len(indices)))]
    return [pool[i] for i in sorted(picked)]


def format_chunk(chunk: LegalChunk, max_chars: int) -> str:
    """Review block: id, Act, unit, title, page, Chapter/Part and (optionally truncated) text."""
    flags = " | REPEALED" if chunk.repealed else ""
    lines = [
        f"=== {chunk.chunk_id} | {chunk.act} {chunk.unit_type} {chunk.section_num}: {chunk.section_title}"
        f" | page {chunk.page}{flags}"
    ]
    context = " / ".join(x for x in (chunk.chapter, chunk.part) if x)
    lines += [f"    [{context}]"] if context else []
    text = chunk.text
    if max_chars and len(text) > max_chars:
        text = f"{text[:max_chars]} [... {len(text) - max_chars} more chars]"
    return "\n".join([*lines, text, ""])


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI: print samples from chunks.json; exit 2 if it has not been built."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-act", type=int, default=5, help="samples per Act (default 5)")
    parser.add_argument("--act", help="only this act slug, e.g. employment-act")
    parser.add_argument("--section", help="show this section/article number (all matches), e.g. 41A")
    parser.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    parser.add_argument("--max-chars", type=int, default=1500, help="truncate text; 0 = full text")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    if not settings.chunks_path.exists():
        print(f"{settings.chunks_path} not found: run python -m backend.app.ingestion.build_corpus", file=sys.stderr)
        return 2
    chunks = select(load_chunks(settings.chunks_path), args.per_act, args.act, args.section, args.seed)
    for chunk in chunks:
        print(format_chunk(chunk, args.max_chars))
    return 0
