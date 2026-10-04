"""Keep citations, numbers and glossary terms out of machine translation by swapping them for placeholders."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.lang.glossary import Glossary, render


@dataclass(frozen=True)
class PlaceholderStyle:
    """How a placeholder is written into model input, and a tolerant pattern to find it in model output."""

    template: str
    pattern: re.Pattern[str]


# Tried in order: a segment that loses a placeholder is retried once with the next style. Measured on opus-mt-en-sw:
# "ZX0Q", "QZ0", "XX0" and "#0" came back intact in 3/3 sentences; "⟦0⟧", "[0]", "{0}", "<0>" and "__0__" in 0/3.
STYLES: tuple[PlaceholderStyle, ...] = (
    PlaceholderStyle("ZX{}Q", re.compile(r"\bZX\s*(\d+)\s*Q\b")),
    PlaceholderStyle("#{}", re.compile(r"#\s*(\d+)\b")),
)

_NUM_REF = r"\d+[A-Za-z]?(?:\s?\(\w{1,4}\))*"
_CITATION = (
    rf"\b(?:sections?|ss?\.|secs?\.?|articles?|arts?\.)\s*{_NUM_REF}(?:\s*(?:,|and|or|to|-|\u2013)\s*{_NUM_REF})*"
)
_CAP = r"\bcap\.?\s*\d+[A-Za-z]?\b"
_NUMBER = r"\d+(?:[.,/:-]\d+)*"
_LETTER_PLACEHOLDER = r"\[[^\[\]\n]{1,40}\]"  # "[Your Name]", "[Date]": left for the user to fill in


@dataclass(frozen=True)
class Masked:
    """Masked text plus, per placeholder index, the source text and what it unmasks to."""

    text: str
    originals: tuple[str, ...]
    replacements: tuple[str, ...]
    style: PlaceholderStyle


def _phrase(words: str, tail: str) -> str:
    """Whole-word regex for a multi-word name plus an optional tail, tolerant of punctuation/spacing between words."""
    return r"\b" + r"\W+".join(map(re.escape, re.findall(r"\w+", words))) + tail + r"\b"


class Protector:
    """Masks letter placeholders, Act names (+ year), section/article refs, Cap numbers, numbers, glossary terms."""

    def __init__(self, act_names: Sequence[str], glossary: Glossary | None) -> None:
        self._glossary = glossary
        acts = [_phrase(n, r"(?:,?\s*\d{4})?") for n in sorted(act_names, key=len, reverse=True)]
        terms = [_phrase(t, r"(?:e?s)?") for t in sorted(glossary.terms, key=len, reverse=True)] if glossary else []
        term_group = [f"(?P<term>{'|'.join(terms)})"] if terms else []
        alternatives = [_LETTER_PLACEHOLDER, *acts, _CITATION, _CAP, *term_group, _NUMBER]
        # Alternation order is precedence: an Act title beats a glossary word inside it ("Land Act" vs "land").
        self._pattern = re.compile("|".join(alternatives), re.IGNORECASE)

    def mask(self, text: str, style: PlaceholderStyle = STYLES[0]) -> Masked:
        """Replace every protected span with style's placeholder; glossary spans unmask to 'sw [en]'."""
        originals: list[str] = []
        replacements: list[str] = []
        glossary = self._glossary

        def swap(match: re.Match[str]) -> str:
            found = match.group()
            originals.append(found)
            if glossary is not None and match.lastgroup == "term":
                replacements.append(render(glossary.lookup(found), found))
            else:
                replacements.append(found)
            return style.template.format(len(originals) - 1)

        masked = self._pattern.sub(swap, text)
        return Masked(masked, tuple(originals), tuple(replacements), style)


def unmask(text: str, masked: Masked) -> tuple[str, list[str]]:
    """Put protected spans back; also return the source text of every placeholder the translation lost."""
    seen: set[int] = set()

    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index >= len(masked.replacements):
            return match.group()
        seen.add(index)
        return masked.replacements[index]

    restored = masked.style.pattern.sub(restore, text)
    return restored, [orig for i, orig in enumerate(masked.originals) if i not in seen]
