"""Legal-aware parser: page text -> one LegalChunk per section, article or schedule (see docs/PARSING_NOTES.md)."""

import re
import unicodedata
from dataclasses import dataclass, field

from backend.app.config import ActSpec, get_settings
from backend.app.ingestion.profiles import DEFAULT_PROFILE, ParserProfile, profile_for
from backend.app.models import LegalChunk

# Curly quotes -> straight; en dash, figure dash, horizontal bar, minus, hyphen -> "-". The em dash (U+2014) is kept.
_CHAR_MAP = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u2013": "-",
        "\u2012": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u2010": "-",
    }
)
_SPACES = re.compile(r"\s+")
_PAGE_NUMBER = re.compile(r"^\d{1,4}$")
# TOC entries: heading-like line ending in a page number, or any dot-leader line (wrapped entries).
_TOC_LINE = re.compile(
    r"^(?:\d{1,4}[A-Z]{0,3}\.\s|Part\s|PART\s|Chapter\s|CHAPTER\s|(?:[A-Z]+\s)?SCHEDULE\b).*\s\d{1,4}$|\.{3,}\s*\d{1,4}$"
)
_TOC_MIN_RUN = 3
_TOC_MAX_GAP = 2
_NOTE_MAX_LINES = 8
_WRAP_MIN_CHARS = 60
_TITLE_MAX_CHARS = 90
_TERMINAL = (".", ";", ":", "]", "—")
_MARKER = re.compile(r"^(?:\((?:\d+[A-Z]*|[a-z]{1,4})\)\s|[\"'])")
_REPEAL_NOTE = re.compile(r"^\[?\s*(?:repealed|deleted|spent)(?:\s+(?:by|vide|under)\b[^\]]*)?\s*[\].;]*$", re.I)
_ORDINALS = ("FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH", "TENTH")


@dataclass(frozen=True)
class Line:
    """One cleaned text line and the PDF page it came from."""

    page: int
    text: str


@dataclass
class _Unit:
    num: str
    title: str
    page: int
    chapter: str = ""
    part: str = ""
    schedule_no: int = 0
    lines: list[str] = field(default_factory=list)


def normalise(text: str) -> str:
    """NFKC, straight quotes, ASCII hyphens (em dash kept), collapsed whitespace."""
    return _SPACES.sub(" ", unicodedata.normalize("NFKC", text).translate(_CHAR_MAP)).strip()


def is_noise(line: str, profile: ParserProfile = DEFAULT_PROFILE) -> bool:
    """True for blank lines, running headers, "[Rev. ...]" lines and dot-leader TOC entries."""
    text = line.strip()
    return not text or bool(profile.header.match(text)) or any(p.search(text) for p in profile.noise)


def is_repealed(text: str) -> bool:
    """True when every line of the text is only a repeal/deletion/spent note."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and all(_REPEAL_NOTE.match(line) for line in lines)


def num_key(num: str) -> tuple[int, str]:
    """Sort key for section numbers: 41 < 41A < 41B < 42."""
    digits = re.match(r"\d+", num)
    return (int(digits.group()), num[digits.end() :]) if digits else (0, num)


def _is_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) >= 0.8 * len(letters)


def _title_like(text: str) -> bool:
    return 2 <= len(text) <= _TITLE_MAX_CHARS and text[0].isupper() and not text.endswith((*_TERMINAL, ",", "-"))


def _heading_title_ok(title: str) -> bool:
    return (title[0].isupper() or title[0] in "[\"'") and not title.endswith((",", ";"))


def _drop_toc_runs(lines: list[Line]) -> list[Line]:
    marks = [i for i, line in enumerate(lines) if _TOC_LINE.search(line.text)]
    dropped: set[int] = set()
    run: list[int] = []
    for i in [*marks, -1]:
        if run and (i == -1 or i - run[-1] > _TOC_MAX_GAP + 1):
            if len(run) >= _TOC_MIN_RUN:
                dropped.update(range(run[0], run[-1] + 1))
            run = []
        run.append(i)
    return [line for i, line in enumerate(lines) if i not in dropped]


def _strip_notes(lines: list[Line], profile: ParserProfile) -> list[Line]:
    kept: list[Line] = []
    i = 0
    while i < len(lines):
        if profile.note_start.match(lines[i].text):
            window = lines[i : i + _NOTE_MAX_LINES]
            end = next((j for j, line in enumerate(window) if line.text.rstrip(".").endswith("]")), None)
            if end is not None:
                i += end + 1
                continue
        kept.append(lines[i])
        i += 1
    return kept


def clean_lines(pages: list[tuple[int, str]], profile: ParserProfile = DEFAULT_PROFILE) -> list[Line]:
    """Normalised body lines: no page numbers, TOC runs, headers, noise or editorial amendment notes."""
    lines: list[Line] = []
    for page_no, text in pages:
        raw = [normalise(line) for line in text.splitlines()]
        raw = [line for line in raw if line]
        while raw and _PAGE_NUMBER.match(raw[-1]):
            raw.pop()
        lines.extend(Line(page_no, line) for line in raw)
    lines = [line for line in _drop_toc_runs(lines) if not is_noise(line.text, profile)]
    return _strip_notes(lines, profile)


class _Builder:
    """Line-by-line state machine: Chapter/Part tracking, unit boundaries, Schedules and skipped blocks."""

    def __init__(self, profile: ParserProfile, max_gap: int) -> None:
        self.profile = profile
        self.max_gap = max_gap
        self.units: list[_Unit] = []
        self.current: _Unit | None = None
        self.chapter = ""
        self.part = ""
        self.pending: str | None = None
        self.mode = "body"
        self.last_key: tuple[int, str] | None = None

    def feed(self, line: Line) -> None:
        """Route one line to the handler for its kind."""
        text, p = line.text, self.profile
        schedule = p.schedule.match(text)
        if schedule:
            self._start_schedule(line, schedule["ordinal"])
        elif p.skip_start.match(text):
            self.close()
            self.mode = "skip"
        elif self.mode == "schedule":
            self._schedule_text(text)
        elif self.mode == "body":
            self._body_line(line)

    def close(self) -> None:
        """Finish the current unit, dropping a trailing cross-heading line (one that follows a finished sentence)."""
        unit = self.current
        if unit is None:
            return
        lines = unit.lines
        if not unit.schedule_no and lines and _title_like(lines[-1]):
            previous_ends = lines[-2].endswith(_TERMINAL) if len(lines) >= 2 else is_repealed(unit.title)
            if previous_ends:
                lines.pop()
        self.units.append(unit)
        self.current = None

    def _body_line(self, line: Line) -> None:
        text, p = line.text, self.profile
        if p.chapter is not None and p.chapter.match(text):
            self.close()
            self.chapter, self.part, self.pending = text, "", "chapter"
        elif p.part.match(text):
            self.close()
            self.part, self.pending = text, "part"
        elif (heading := self._heading(text)) is not None:
            self.close()
            self.current = _Unit(heading[0], heading[1], line.page, self.chapter, self.part)
            self.last_key = num_key(heading[0])
            self.pending = "title" if len(text) >= _WRAP_MIN_CHARS else None
        else:
            self._body_text(text)

    def _heading(self, text: str) -> tuple[str, str] | None:
        match = self.profile.heading.match(text)
        if match is None or not _heading_title_ok(match["title"]):
            return None
        key = num_key(match["num"])
        last = self.last_key
        in_sequence = key[0] <= self.max_gap if last is None else last < key and key[0] <= last[0] + self.max_gap
        return (match["num"], match["title"].rstrip(".") or match["title"]) if in_sequence else None

    def _body_text(self, text: str) -> None:
        pending, self.pending = self.pending, None
        if pending == "title" and self.current is not None and text[0].islower():
            self.current.title = f"{self.current.title} {text}"
        elif pending == "chapter" and _title_like(text) and _is_upper(text):
            self.chapter = self._extend(self.chapter, text)
            self.pending = "chapter"
        elif pending == "part" and _title_like(text) and self._matches_part_case(text):
            self.part = self._extend(self.part, text)
            self.pending = "part"
        elif self.current is not None:
            self.current.lines.append(text)

    def _matches_part_case(self, text: str) -> bool:
        return not _is_upper(self.part.partition(" - ")[2]) or _is_upper(text)

    @staticmethod
    def _extend(heading: str, text: str) -> str:
        return f"{heading} {text}" if " - " in heading else f"{heading} - {text}"

    def _start_schedule(self, line: Line, ordinal: str | None) -> None:
        self.close()
        self.mode, self.pending = "schedule", "schedule"
        if ordinal in _ORDINALS:
            number, label = _ORDINALS.index(ordinal) + 1, f"{ordinal.title()} Schedule"
        else:
            number, label = 1, "Schedule"
        self.current = _Unit(label, "", line.page, schedule_no=number)

    def _schedule_text(self, text: str) -> None:
        pending, self.pending = self.pending, None
        if self.current is None:
            return
        if pending == "schedule" and _is_upper(text) and self.profile.heading.match(text) is None:
            self.current.title = text
        else:
            self.current.lines.append(text)


def _starts_paragraph(line: str, profile: ParserProfile) -> bool:
    heading = profile.heading.match(line)
    return (
        bool(_MARKER.match(line))
        or (heading is not None and _heading_title_ok(heading["title"]))
        or bool(profile.part.match(line))
        or (_is_upper(line) and sum(c.isalpha() for c in line) >= 4)
    )


def join_lines(lines: list[str], profile: ParserProfile = DEFAULT_PROFILE) -> str:
    """Join wrapped lines into paragraphs, keeping subsection markers and numbered items on new lines."""
    paragraphs: list[str] = []
    for line in lines:
        if not paragraphs or _starts_paragraph(line, profile):
            paragraphs.append(line)
        elif re.search(r"[A-Za-z]-$", paragraphs[-1]):
            paragraphs[-1] += line
        else:
            paragraphs[-1] += " " + line
    return "\n".join(paragraphs)


def _chunk_ids(units: list[_Unit], slug: str) -> list[str]:
    seen: dict[str, int] = {}
    ids = []
    for unit in units:
        base = f"{slug}-sch{unit.schedule_no}" if unit.schedule_no else f"{slug}-{unit.num.lower()}"
        seen[base] = seen.get(base, 0) + 1
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return ids


def parse_act(pages: list[tuple[int, str]], spec: ActSpec, sha256: str, max_gap: int | None = None) -> list[LegalChunk]:
    """Parse one Act's page texts into chunks in document order."""
    profile = profile_for(spec.slug)
    builder = _Builder(profile, max_gap if max_gap is not None else get_settings().heading_max_gap)
    for line in clean_lines(pages, profile):
        builder.feed(line)
    builder.close()
    chunks = []
    for unit, chunk_id in zip(builder.units, _chunk_ids(builder.units, spec.slug), strict=True):
        text = join_lines(unit.lines, profile)
        title_repealed = is_repealed(unit.title)
        if title_repealed:
            text = "\n".join(part for part in (unit.title, text) if part)
        chunks.append(
            LegalChunk(
                chunk_id=chunk_id,
                act=spec.name,
                act_slug=spec.slug,
                act_year=spec.year,
                unit_type="schedule" if unit.schedule_no else profile.unit_type,
                chapter=unit.chapter,
                part=unit.part,
                section_num=unit.num,
                section_title=unit.title,
                text=text,
                page=unit.page,
                repealed=title_repealed or is_repealed(text),
                source_sha256=sha256,
            )
        )
    return chunks
