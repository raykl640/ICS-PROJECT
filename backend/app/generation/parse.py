"""Incremental splitter of the LLM answer into its three headed sections (§7.3), tolerant of header variants."""

import re
from dataclasses import dataclass
from typing import Literal

from backend.app.models import ParsedResponse

Section = Literal["rights", "steps", "letter"]

_NAMES: dict[str, Section] = {"rights explanation": "rights", "recommended steps": "steps", "formal letter": "letter"}
# "## Rights Explanation", "**RIGHTS EXPLANATION**", "### RIGHTS EXPLANATION:", "**Formal Letter:** Dear ..." (inline).
_HEADER = re.compile(
    r"^[ \t#*_]*(?P<name>rights explanation|recommended steps|formal letter)[ \t*_]*(?::[ \t*_]*(?P<rest>.*?))?[ \t]*$",
    re.IGNORECASE,
)
_LEADING_MARKUP = re.compile(r"^[ \t#*_]*")
_HEADER_TAIL = re.compile(r"[ \t*_]*(?::.*)?")


@dataclass(frozen=True)
class SectionDelta:
    """Text appended to one section."""

    section: Section
    text: str


def _could_be_header(partial: str) -> bool:
    """True while an unfinished line could still turn out to be a header line."""
    core = _LEADING_MARKUP.sub("", partial).lower()
    for name in _NAMES:
        if name.startswith(core.rstrip(" \t*_")):
            return True
        if core.startswith(name) and _HEADER_TAIL.fullmatch(core[len(name) :]):
            return True
    return False


class SectionSplitter:
    """Feed streamed tokens; body text is emitted as soon as its line cannot be a header, header lines switch section.

    Text before the first header goes to rights; a repeated header appends to its section.
    """

    def __init__(self) -> None:
        self._current: Section = "rights"
        self._pending = ""
        self._in_body_line = False
        self._parts: dict[Section, list[str]] = {"rights": [], "steps": [], "letter": []}
        self._seen: set[Section] = set()

    def feed(self, token: str) -> list[SectionDelta]:
        """Consume one token and return the section deltas it completes."""
        events: list[SectionDelta] = []
        for piece in re.split(r"(?<=\n)", token):
            if piece:
                events += self._consume(piece)
        return events

    def finalize(self) -> ParsedResponse:
        """Flush any unfinished line and return the stripped sections; format_ok iff all three headers appeared."""
        if self._pending:
            line, self._pending = self._pending, ""
            self._line(line)
        return ParsedResponse(
            rights="".join(self._parts["rights"]).strip(),
            steps="".join(self._parts["steps"]).strip(),
            letter="".join(self._parts["letter"]).strip(),
            format_ok=self._seen == set(_NAMES.values()),
        )

    def _consume(self, piece: str) -> list[SectionDelta]:
        """Handle a piece holding at most one newline, at its end."""
        ends_line = piece.endswith("\n")
        if self._in_body_line:
            self._in_body_line = not ends_line
            return self._emit(piece)
        self._pending += piece
        if ends_line:
            line, self._pending = self._pending, ""
            return self._line(line)
        if not _could_be_header(self._pending):
            text, self._pending = self._pending, ""
            self._in_body_line = True
            return self._emit(text)
        return []

    def _line(self, line: str) -> list[SectionDelta]:
        """Classify a complete (buffered) line: switch section on a header, else emit it as body text."""
        match = _HEADER.match(line.rstrip("\n"))
        if not match:
            return self._emit(line)
        self._current = _NAMES[match["name"].lower()]
        self._seen.add(self._current)
        rest = match["rest"]
        return self._emit(rest + line[len(line.rstrip("\n")) :]) if rest else []

    def _emit(self, text: str) -> list[SectionDelta]:
        """Append text to the current section."""
        self._parts[self._current].append(text)
        return [SectionDelta(self._current, text)]


def split_sections(text: str) -> ParsedResponse:
    """Split a complete answer into its sections."""
    splitter = SectionSplitter()
    splitter.feed(text)
    return splitter.finalize()
