"""Placeholder masking: what is protected, precedence, tolerant unmasking, lost-placeholder detection."""

import pytest

from backend.app.lang.glossary import Glossary
from backend.app.lang.protect import STYLES, PlaceholderStyle, Protector, unmask

GLOSSARY = Glossary("needs_human_review", {"tenant": "mpangaji", "notice": "notisi", "land": "ardhi"})
PROTECTOR = Protector(["Employment Act", "Land Act", "Constitution of Kenya"], GLOSSARY)


def _originals(text: str) -> list[str]:
    return list(PROTECTOR.mask(text).originals)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("under the Employment Act, 2007 you", ["Employment Act, 2007"]),
        ("the Constitution of Kenya 2010 says", ["Constitution of Kenya 2010"]),
        ("see Section 41(2)(a) now", ["Section 41(2)(a)"]),
        ("see s. 45 and ss. 41 and 43", ["s. 45", "ss. 41 and 43"]),
        ("see sections 35, 36 to 38 here", ["sections 35, 36 to 38"]),
        ("Article 41 protects", ["Article 41"]),
        ("Cap. 226 and Cap 16A", ["Cap. 226", "Cap 16A"]),
        ("pay KES 5,000 within 30 days of 12/03/2024", ["5,000", "30", "12/03/2024"]),
        ("the Tenants got Notice", ["Tenants", "Notice"]),
        ("the Land Act protects land", ["Land Act", "land"]),
        ("a landlord and the Acts. 4", ["4"]),
    ],
)
def test_protected_spans(text: str, expected: list[str]) -> None:
    assert _originals(text) == expected


def test_glossary_terms_unmask_to_bracketed_swahili() -> None:
    masked = PROTECTOR.mask("The tenant got notice under s. 4.")
    assert masked.text == "The ZX0Q got ZX1Q under ZX2Q."
    assert masked.replacements == ("mpangaji [tenant]", "notisi [notice]", "s. 4")


def test_roundtrip_without_translation_restores_citations() -> None:
    text = "Under the Employment Act, 2007, Section 41(2) requires notice; see Article 41 and Cap 226."
    masked = PROTECTOR.mask(text)
    restored, missing = unmask(masked.text, masked)
    assert missing == []
    assert restored == text.replace("notice", "notisi [notice]")


@pytest.mark.parametrize(("style", "spaced"), list(zip(STYLES, ["ZX 0 Q in ZX1 Q.", "# 0 in #1."], strict=True)))
def test_unmask_tolerates_spacing_inside_placeholders(style: PlaceholderStyle, spaced: str) -> None:
    masked = PROTECTOR.mask("Section 41 in 2007.", style)
    assert unmask(spaced, masked) == ("Section 41 in 2007.", [])


def test_lost_placeholder_is_reported() -> None:
    masked = PROTECTOR.mask("Section 41 needs notice.")
    restored, missing = unmask("ZX1Q inahitajika.", masked)
    assert restored == "notisi [notice] inahitajika."
    assert missing == ["Section 41"]


def test_unknown_placeholder_index_is_left_alone() -> None:
    masked = PROTECTOR.mask("Section 41.")
    assert unmask("ZX0Q ZX7Q", masked) == ("Section 41 ZX7Q", [])


def test_text_without_protected_spans_is_unchanged() -> None:
    masked = PROTECTOR.mask("Write to your employer.")
    assert (masked.text, masked.originals) == ("Write to your employer.", ())


def test_without_glossary_or_acts_only_citations_and_numbers_are_masked() -> None:
    masked = Protector([], None).mask("The tenant got notice in 2020 under s. 4 of the Employment Act.")
    assert masked.originals == ("2020", "s. 4")
    assert masked.replacements == masked.originals
