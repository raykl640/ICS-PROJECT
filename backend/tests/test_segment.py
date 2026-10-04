"""Segmentation for translation: lossless join, line/sentence/word boundaries, size limits (invented text)."""

import pytest

from backend.app.generation.budget import est_tokens
from backend.app.lang.segment import Part, segment

PER_WORD = 1.4


def _translatable(parts: list[Part]) -> list[str]:
    return [p.text for p in parts if p.translate]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "One sentence.",
        "Dear Sir,\n\nI write about my dismissal.\nYours faithfully,\n[Your Name]\n",
        "1. Ask for reasons.\n2. Keep copies.\n  - Write to the Labour Officer.  \n",
        "  leading and trailing spaces  ",
        "First. Second!  Third? Fourth.",
    ],
)
def test_join_is_lossless(text: str) -> None:
    assert "".join(p.text for p in segment(text, 350, PER_WORD)) == text


def test_lines_are_separate_segments() -> None:
    parts = segment("Dear Sir,\n\nI was dismissed.\nYours faithfully,", 350, PER_WORD)
    assert _translatable(parts) == ["Dear Sir,", "I was dismissed.", "Yours faithfully,"]
    assert [p.text for p in parts if not p.translate] == ["\n\n", "\n"]


def test_list_markers_are_not_translated() -> None:
    parts = segment("1. Ask for reasons.\n- Keep copies.\n• Sign nothing.", 350, PER_WORD)
    assert _translatable(parts) == ["Ask for reasons.", "Keep copies.", "Sign nothing."]
    assert "1. " in [p.text for p in parts if not p.translate]


def test_short_line_stays_one_segment() -> None:
    line = "You were dismissed. The employer must give reasons. You may complain."
    assert _translatable(segment(line, 350, PER_WORD)) == [line]


def test_long_line_splits_at_sentence_boundaries() -> None:
    sentences = [f"Sentence number {word} is here." for word in ("one", "two", "three", "four", "five", "six")]
    parts = segment(" ".join(sentences), 20, PER_WORD)
    pieces = _translatable(parts)
    assert len(pieces) > 1
    assert all(est_tokens(p, PER_WORD) <= 20 for p in pieces)
    assert all(p.endswith(".") and p[0].isupper() for p in pieces)


def test_citation_abbreviations_do_not_split_sentences() -> None:
    line = "See s. 41 of Cap. 226 and Section 45. Then act."
    assert _translatable(segment(line, 20, PER_WORD)) == ["See s. 41 of Cap. 226 and Section 45.", "Then act."]


def test_over_long_sentence_splits_into_word_runs() -> None:
    sentence = " ".join(["word"] * 100) + "."
    pieces = _translatable(segment(sentence, 20, PER_WORD))
    assert len(pieces) > 1
    assert all(est_tokens(p, PER_WORD) <= 20 for p in pieces)
    assert " ".join(pieces) == sentence


def test_over_long_sentence_between_short_ones() -> None:
    text = "Short one. " + " ".join(["Long"] * 60) + ". Short two."
    pieces = _translatable(segment(text, 20, PER_WORD))
    assert pieces[0] == "Short one."
    assert pieces[-1] == "Short two."
    assert all(est_tokens(p, PER_WORD) <= 20 for p in pieces)


def test_unpacked_mode_keeps_one_sentence_per_part() -> None:
    line = "You were dismissed. The employer must give reasons. You may complain."
    parts = segment(line, 350, PER_WORD, pack=False)
    assert _translatable(parts) == ["You were dismissed.", "The employer must give reasons.", "You may complain."]
    assert "".join(p.text for p in parts) == line
