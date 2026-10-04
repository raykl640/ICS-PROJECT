"""EN→SW legal glossary (unverified, status needs_human_review): terms render as "Kiswahili term [English term]"."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Glossary:
    """Lower-case English term → Kiswahili rendering, plus the review status from the file."""

    status: str
    terms: Mapping[str, str]

    def lookup(self, english: str) -> str:
        """Kiswahili for a matched English term (case, punctuation between words and a plural -s/-es ignored)."""
        key = " ".join(re.findall(r"\w+", english.lower()))
        for candidate in (key, key.removesuffix("es"), key.removesuffix("s")):
            if candidate in self.terms:
                return self.terms[candidate]
        raise KeyError(english)


def render(swahili: str, english: str) -> str:
    """'Kiswahili [English]' so the user can always see the original legal term."""
    return f"{swahili} [{english}]"


def load_glossary(path: Path) -> Glossary:
    """Read glossary.json, requiring a status and non-empty, normalised lower-case terms."""
    data = json.loads(path.read_text(encoding="utf-8"))
    terms: dict[str, str] = data["terms"]
    for english, swahili in terms.items():
        if english != " ".join(re.findall(r"\w+", english.lower())) or not swahili.strip():
            raise ValueError(f"{path.name}: bad glossary entry {english!r}")
    if not terms:
        raise ValueError(f"{path.name}: no terms")
    return Glossary(status=str(data["status"]), terms=terms)
