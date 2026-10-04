"""Per-Act parsing profiles: heading, Part/Chapter, Schedule and noise patterns (see docs/PARSING_NOTES.md)."""

import re
from dataclasses import dataclass, field, replace
from typing import Literal

# Patterns run on normalised text (unicode dashes already mapped to "-").
HEADING_RE = re.compile(r"^(?P<num>\d{1,4}[A-Z]{0,3})\.\s+(?P<title>\S.*)$")
PART_RE = re.compile(r"^Part\s+(?:[IVXLC]+[A-Z]?|\d+[A-Z]?)\s+-\s+\S.*$")
CHAPTER_RE = re.compile(r"^Chapter\s+[A-Z][A-Za-z]+$")
SCHEDULE_RE = re.compile(r"^(?:(?P<ordinal>[A-Z]+)\s+)?SCHEDULE(?:\s*\[[^\]]*\])?$")
# Running headers carry "Kenya" on the outer edge; a bare "(Cap. 63)" line end is body text (e.g. a Schedule title).
HEADER_RE = re.compile(r"^(?:.{3,160}\(Cap\.\s?\d+[A-Z]?\)\s+Kenya|Kenya\s+.{3,160}\(Cap\.\s?\d+[A-Z]?\))$")
CONSTITUTION_HEADER_RE = re.compile(r"^(?:Constitution of Kenya\s+Kenya|Kenya\s+Constitution of Kenya)$")
# Editorial amendment history ("[Act No. 19 of 2015, s. 148.]"), possibly wrapped over several lines.
NOTE_START_RE = re.compile(r"^\[(?:Act No\.|L\.\s?N\.|LN\b|Amended by|Revised by|Corrigendum)")
# Blocks that are not part of the Act; skipped until the next Schedule heading.
SKIP_START_RE = re.compile(r"^INDEX TO THE\b")
NOISE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\[Rev\.\s.*\]"),
    re.compile(r"\.{5,}\s*\d{1,4}$"),
)


@dataclass(frozen=True)
class ParserProfile:
    """How one statute's layout is recognised; the default fits the Kenya Law / Laws.Africa format."""

    unit_type: Literal["section", "article"] = "section"
    heading: re.Pattern[str] = HEADING_RE
    part: re.Pattern[str] = PART_RE
    chapter: re.Pattern[str] | None = None
    schedule: re.Pattern[str] = SCHEDULE_RE
    header: re.Pattern[str] = HEADER_RE
    note_start: re.Pattern[str] = NOTE_START_RE
    skip_start: re.Pattern[str] = SKIP_START_RE
    noise: tuple[re.Pattern[str], ...] = field(default=NOISE_RES)


DEFAULT_PROFILE = ParserProfile()
PROFILES: dict[str, ParserProfile] = {
    "constitution-of-kenya": replace(
        DEFAULT_PROFILE, unit_type="article", chapter=CHAPTER_RE, header=CONSTITUTION_HEADER_RE
    ),
}


def profile_for(act_slug: str) -> ParserProfile:
    """Profile for an Act, falling back to the default layout."""
    return PROFILES.get(act_slug, DEFAULT_PROFILE)
