"""Glossary file contract: review status, size, normalised keys, 'Kiswahili [English]' rendering."""

import json
import re
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.lang.glossary import Glossary, load_glossary, render

REQUIRED = [
    *("dismissal", "notice", "tenant", "landlord", "eviction", "bail", "arrest", "warrant", "compensation"),
    *("contract", "wages", "consumer", "refund", "warranty", "title deed", "appeal", "complaint", "summons"),
]


def test_shipped_glossary_is_flagged_and_large_enough() -> None:
    glossary = load_glossary(Settings().glossary_path)
    assert glossary.status == "needs_human_review"
    assert len(glossary.terms) >= 60
    assert set(REQUIRED) <= set(glossary.terms)


def test_human_todo_mentions_glossary_review() -> None:
    todo = (Path(__file__).resolve().parents[2] / "docs" / "HUMAN_TODO.md").read_text(encoding="utf-8")
    assert "glossary.json" in todo


def test_render_brackets_the_english_term() -> None:
    assert render("mpangaji", "tenant") == "mpangaji [tenant]"
    glossary = load_glossary(Settings().glossary_path)
    pattern = re.compile(r"^[^\[\]]+ \[[^\[\]]+\]$")
    assert all(pattern.match(render(sw, en)) for en, sw in glossary.terms.items())


@pytest.mark.parametrize(
    ("found", "expected"),
    [("Tenant", "mpangaji"), ("tenants", "mpangaji"), ("witnesses", "shahidi"), ("Title-Deed", "hati miliki")],
)
def test_lookup_ignores_case_plural_and_punctuation(found: str, expected: str) -> None:
    glossary = Glossary("needs_human_review", {"tenant": "mpangaji", "witness": "shahidi", "title deed": "hati miliki"})
    assert glossary.lookup(found) == expected


def test_lookup_unknown_term_raises() -> None:
    with pytest.raises(KeyError):
        Glossary("x", {"tenant": "mpangaji"}).lookup("landlord")


@pytest.mark.parametrize("terms", [{}, {"Tenant": "mpangaji"}, {"title  deed": "x"}, {"tenant": " "}])
def test_load_rejects_bad_entries(tmp_path: Path, terms: dict[str, str]) -> None:
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"status": "needs_human_review", "terms": terms}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_glossary(path)
