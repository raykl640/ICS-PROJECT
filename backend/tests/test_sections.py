"""SectionSplitter on split tokens and malformed model outputs (all answer text is invented)."""

import pytest

from backend.app.generation.parse import SectionDelta, SectionSplitter, split_sections
from backend.app.models import ParsedResponse
from backend.tests.fakes import DEFAULT_SCRIPT

WELL_FORMED = "## RIGHTS EXPLANATION\nYou have rights.\n## RECOMMENDED STEPS\n1. Act.\n## FORMAL LETTER\nDear Sir,\n"


def _feed_all(tokens: list[str] | tuple[str, ...]) -> tuple[list[SectionDelta], ParsedResponse]:
    splitter = SectionSplitter()
    events = [event for token in tokens for event in splitter.feed(token)]
    return events, splitter.finalize()


def test_default_fake_script_with_headers_split_across_tokens() -> None:
    events, parsed = _feed_all(DEFAULT_SCRIPT)
    assert parsed.rights == "You have rights under Sample Act, Section 12."
    assert parsed.steps == "1. Write to the other party."
    assert parsed.letter == "Dear Sir or Madam,"
    assert parsed.format_ok
    assert not any("##" in e.text or "RIGHTS" in e.text for e in events)


@pytest.mark.parametrize("size", [1, 2, 3, 7])
def test_any_token_split_gives_the_same_result(size: int) -> None:
    tokens = [WELL_FORMED[i : i + size] for i in range(0, len(WELL_FORMED), size)]
    events, parsed = _feed_all(tokens)
    assert parsed == split_sections(WELL_FORMED)
    assert "".join(e.text for e in events if e.section == "steps").strip() == "1. Act."


def test_body_text_streams_before_its_line_ends() -> None:
    splitter = SectionSplitter()
    splitter.feed("## RIGHTS EXPLANATION\n")
    assert splitter.feed("You have") == [SectionDelta("rights", "You have")]
    assert splitter.feed(" rights") == [SectionDelta("rights", " rights")]


def test_possible_header_is_held_until_decided() -> None:
    splitter = SectionSplitter()
    assert splitter.feed("##") == []
    assert splitter.feed(" Rec") == []
    assert splitter.feed("ommended Steps\n") == []
    assert splitter.feed("1. Go") == [SectionDelta("steps", "1. Go")]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (  # markdown bold, title case, colon variants
            "**RIGHTS EXPLANATION**\nA.\n### Recommended Steps:\nB.\n**Formal Letter:**\nC.",
            ParsedResponse(rights="A.", steps="B.", letter="C.", format_ok=True),
        ),
        (  # reordered headers
            "## FORMAL LETTER\nC.\n## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.",
            ParsedResponse(rights="A.", steps="B.", letter="C.", format_ok=True),
        ),
        (  # duplicated header appends
            "## RIGHTS EXPLANATION\nA1.\n## RECOMMENDED STEPS\nB.\n## RIGHTS EXPLANATION\nA2.\n## FORMAL LETTER\nC.",
            ParsedResponse(rights="A1.\nA2.", steps="B.", letter="C.", format_ok=True),
        ),
        (  # missing letter header
            "## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.",
            ParsedResponse(rights="A.", steps="B.", letter="", format_ok=False),
        ),
        (  # no headers at all: everything is rights
            "You have rights.\n1. Do this.\nDear Sir,",
            ParsedResponse(rights="You have rights.\n1. Do this.\nDear Sir,", format_ok=False),
        ),
        (  # preamble before the first header stays in rights
            "Here is my answer.\n## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.\n## FORMAL LETTER\nC.",
            ParsedResponse(rights="Here is my answer.\nA.", steps="B.", letter="C.", format_ok=True),
        ),
        (  # trailing text after the letter stays in the letter
            "## RIGHTS EXPLANATION\nA.\n## RECOMMENDED STEPS\nB.\n## FORMAL LETTER\nC.\n\nGood luck.",
            ParsedResponse(rights="A.", steps="B.", letter="C.\n\nGood luck.", format_ok=True),
        ),
        (  # header with inline content after a colon
            "Rights Explanation: A.\nRecommended steps: B.\n__Formal letter__: C.",
            ParsedResponse(rights="A.", steps="B.", letter="C.", format_ok=True),
        ),
        (  # words that merely start like a header are body text
            "## RIGHTS EXPLANATION\nRights explanation is short.\n## RECOMMENDED STEPS\nB.\n## FORMAL LETTER\nC.",
            ParsedResponse(rights="Rights explanation is short.", steps="B.", letter="C.", format_ok=True),
        ),
        (  # empty output
            "",
            ParsedResponse(format_ok=False),
        ),
    ],
)
def test_malformed_outputs(text: str, expected: ParsedResponse) -> None:
    assert split_sections(text) == expected
    assert _feed_all(list(text))[1] == expected  # one character per token


def test_unfinished_last_line_is_classified_on_finalize() -> None:
    splitter = SectionSplitter()
    splitter.feed("## RIGHTS EXPLANATION\nA.\n## FORMAL LETTER")
    assert splitter.finalize() == ParsedResponse(rights="A.", format_ok=False)
