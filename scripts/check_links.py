#!/usr/bin/env python
"""Check that every relative link (and #anchor) in the project's Markdown files resolves. Exit 1 listing broken ones.

Usage: `python scripts/check_links.py`. External http(s)/mailto links are not fetched (the project is offline).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "node_modules", "legacy", "prompts", ".gates", "test-results", "playwright-report", "dist"}
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def markdown_files(root: Path) -> list[Path]:
    """Project Markdown files outside vendored, generated and private directories."""
    return sorted(p for p in root.rglob("*.md") if not SKIP_DIRS.intersection(p.relative_to(root).parts))


def slug(heading: str) -> str:
    """GitHub-style anchor for a heading."""
    text = re.sub(r"[`*_\[\]()]", "", heading).strip().lower()
    return re.sub(r"\s", "-", re.sub(r"[^\w\- ]", "", text))


def anchors(path: Path) -> set[str]:
    """Anchors defined by the headings of a Markdown file."""
    return {slug(h) for h in _HEADING.findall(_FENCE.sub("", path.read_text(encoding="utf-8")))}


def links(text: str) -> list[str]:
    """Link targets outside code blocks and inline code."""
    return _LINK.findall(_INLINE_CODE.sub("", _FENCE.sub("", text)))


def broken_links(root: Path = ROOT) -> list[str]:
    """'file: target (reason)' for each relative link whose file or anchor does not exist."""
    problems = []
    for md in markdown_files(root):
        for target in links(md.read_text(encoding="utf-8")):
            if re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                continue  # http:, https:, mailto: ...
            file_part, _, anchor = target.partition("#")
            dest = (md.parent / file_part).resolve() if file_part else md
            where = md.relative_to(root)
            if not dest.exists():
                problems.append(f"{where}: {target} (no such file)")
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                problems.append(f"{where}: {target} (no such heading)")
    return problems


def main() -> int:
    """Print broken links; 0 when there are none."""
    problems = broken_links()
    for problem in problems:
        print(problem)
    print(f"{len(markdown_files(ROOT))} Markdown files checked, {len(problems)} broken link(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
