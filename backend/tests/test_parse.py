from pathlib import Path

import pytest

from backend.app.config import ActSpec
from backend.app.ingestion.extract import extract_pages
from backend.app.ingestion.parse import is_noise, is_repealed, normalise, parse_act
from backend.app.ingestion.profiles import DEFAULT_PROFILE, profile_for
from backend.app.models import LegalChunk
from backend.tests.fixtures.synthetic_pdf import SAMPLE_ACT_PAGES, write_pdf

SHA = "0" * 64
SPEC = ActSpec(name="Sample Act", year=2001, file="Sample Act.pdf", cap="999")
CONSTITUTION = ActSpec(name="Constitution of Kenya", year=2010, file="c.pdf", unit="Article")
HEADER = "Sample Act (Cap. 999) Kenya"


def pages_of(*pages: list[str]) -> list[tuple[int, str]]:
    return [(i + 1, "\n".join(lines)) for i, lines in enumerate(pages)]


def by_num(chunks: list[LegalChunk]) -> dict[str, LegalChunk]:
    return {c.section_num: c for c in chunks}


@pytest.fixture(scope="module")
def sample_chunks(tmp_path_factory: pytest.TempPathFactory) -> list[LegalChunk]:
    pdf = write_pdf(tmp_path_factory.mktemp("pdf") / "Sample Act.pdf", SAMPLE_ACT_PAGES)
    return parse_act(extract_pages(pdf), SPEC, SHA)


def test_sample_pdf_yields_sections_and_schedules(sample_chunks: list[LegalChunk]) -> None:
    ids = [c.chunk_id for c in sample_chunks]
    assert ids == [
        "sample-act-1",
        "sample-act-2",
        "sample-act-3",
        "sample-act-4",
        "sample-act-5",
        "sample-act-sch1",
        "sample-act-sch2",
    ]
    assert {c.act for c in sample_chunks} == {"Sample Act"}
    assert {c.act_year for c in sample_chunks} == {2001}
    assert {c.source_sha256 for c in sample_chunks} == {SHA}


def test_toc_entries_never_become_chunks(sample_chunks: list[LegalChunk]) -> None:
    assert all("...." not in c.text and "...." not in c.section_title for c in sample_chunks)
    assert by_num(sample_chunks)["1"].page == 3


def test_part_tracking_joins_wrapped_part_title(sample_chunks: list[LegalChunk]) -> None:
    chunks = by_num(sample_chunks)
    assert chunks["2"].part == "Part I - PRELIMINARY"
    assert chunks["4"].part == "Part II - RIGHTS AND DUTIES OF EMPLOYERS"
    assert chunks["5"].part == "Part II - RIGHTS AND DUTIES OF EMPLOYERS"
    assert chunks["Schedule"].part == ""


def test_subsections_are_kept_on_their_own_lines(sample_chunks: list[LegalChunk]) -> None:
    lines = by_num(sample_chunks)["4"].text.splitlines()
    assert lines[0].startswith("(1) Every worker")
    assert [line.split()[0] for line in lines[:7]] == ["(1)", "(2)", "(a)", "(b)", "(i)", "(ii)", "(3)"]
    assert lines[5] == "(ii) leave taken."


def test_compound_hyphen_at_line_end_is_joined_without_space(sample_chunks: list[LegalChunk]) -> None:
    assert "the co-operation of the employer" in by_num(sample_chunks)["4"].text


def test_wrapped_lines_join_and_definitions_start_new_lines(sample_chunks: list[LegalChunk]) -> None:
    text = by_num(sample_chunks)["2"].text
    assert '"employer" means a person who employs another person under a contract of service;' in text.splitlines()
    assert text.splitlines()[-1] == '"worker" means a person employed for wages.'


def test_editorial_amendment_notes_are_stripped(sample_chunks: list[LegalChunk]) -> None:
    assert all("Act No. 5 of 2010" not in c.text and "2012, s. 3" not in c.text for c in sample_chunks)


def test_repealed_section_is_flagged_and_keeps_its_note(sample_chunks: list[LegalChunk]) -> None:
    chunk = by_num(sample_chunks)["3"]
    assert chunk.repealed
    assert chunk.text == "[Repealed by Act No. 1 of 2015, s. 4.]"
    assert not by_num(sample_chunks)["4"].repealed


def test_running_header_and_page_numbers_are_removed(sample_chunks: list[LegalChunk]) -> None:
    for chunk in sample_chunks:
        assert "(Cap. 999)" not in chunk.text
        assert all(not line.strip().isdigit() for line in chunk.text.splitlines())


def test_multi_page_section_keeps_first_page(sample_chunks: list[LegalChunk]) -> None:
    chunk = by_num(sample_chunks)["4"]
    assert chunk.page == 3
    assert "(3) The records shall be kept for five years." in chunk.text


def test_numbered_list_inside_a_section_is_not_a_heading(sample_chunks: list[LegalChunk]) -> None:
    text = by_num(sample_chunks)["4"].text
    assert "1. Introduction" in text
    assert "2. Background" in text


def test_cross_heading_is_not_appended_to_previous_section(sample_chunks: list[LegalChunk]) -> None:
    assert all("Termination Generally" not in c.text for c in sample_chunks)
    assert by_num(sample_chunks)["4"].text.endswith("The list above is illustrative only.")


def test_unicode_quotes_are_normalised(sample_chunks: list[LegalChunk]) -> None:
    assert "twenty-eight days' written notice" in by_num(sample_chunks)["5"].text


def test_schedules_are_single_chunks_and_repealed_schedule_flagged(sample_chunks: list[LegalChunk]) -> None:
    first, second = sample_chunks[-2:]
    assert first.unit_type == "schedule"
    assert first.section_num == "Schedule"
    assert first.section_title == "FORMS OF NOTICE"
    assert first.text.splitlines() == ["1. Form of notice to a worker", "2. Form of notice to the labour officer"]
    assert not first.repealed
    assert second.section_num == "Second Schedule"
    assert second.repealed


def test_41a_is_ordered_between_41_and_42() -> None:
    pages = pages_of(
        [
            "40. Before",
            "Text of section forty.",
            "41. Notice",
            "Text of section forty-one.",
            "41A. Inserted notice",
            "Text of section forty-one A.",
            "42. After",
            "Text of section forty-two.",
        ]
    )
    chunks = parse_act(pages, SPEC, SHA, max_gap=50)
    assert [c.chunk_id for c in chunks] == ["sample-act-40", "sample-act-41", "sample-act-41a", "sample-act-42"]


def test_lower_numbered_footnote_inside_section_is_not_a_heading() -> None:
    pages = pages_of(
        ["7. Wages", "(1) Wages shall be paid monthly.", "1. See Legal Notice 5 of 2010."],
        ["(2) Wages may be paid weekly by agreement.", "8. Deductions", "No deduction shall be made."],
    )
    chunks = parse_act(pages, SPEC, SHA)
    assert [c.section_num for c in chunks] == ["7", "8"]
    assert "(2) Wages may be paid weekly by agreement." in chunks[0].text


def test_heading_too_far_ahead_is_rejected() -> None:
    pages = pages_of(["1. Short title", "This Act may be cited as X.", "2000. The year of reckoning was long ago."])
    assert [c.section_num for c in parse_act(pages, SPEC, SHA, max_gap=10)] == ["1"]


def test_lowercase_title_is_not_a_heading() -> None:
    pages = pages_of(["1. Short title", "The sum is payable within", "2. months of the demand."])
    chunks = parse_act(pages, SPEC, SHA)
    assert [c.section_num for c in chunks] == ["1"]
    assert chunks[0].text == "The sum is payable within 2. months of the demand."


def test_long_wrapped_heading_title_is_joined() -> None:
    pages = pages_of(
        [
            "33. Debt owed to national government or county government not extinguished",
            "by forfeiture",
            "A forfeiture shall not extinguish any debt.",
        ]
    )
    (chunk,) = parse_act(pages, SPEC, SHA, max_gap=50)
    assert chunk.section_title == "Debt owed to national government or county government not extinguished by forfeiture"
    assert chunk.text == "A forfeiture shall not extinguish any debt."


def test_cross_heading_after_repealed_section_is_dropped() -> None:
    pages = pages_of(["1. Short title", "Text one.", "2. [Repealed by Act No. 5 of 2003, s. 65.]", "Transfer of Cases"])
    chunks = parse_act(pages, SPEC, SHA)
    assert chunks[1].text == "[Repealed by Act No. 5 of 2003, s. 65.]"
    assert chunks[1].repealed


def test_repealed_heading_with_orphan_body_stays_repealed_and_keeps_the_fragment() -> None:
    pages = pages_of(["1. [Repealed by Act No. 3 of 2006, 2nd Sch.;]", "(b) With offences under another Act."])
    (chunk,) = parse_act(pages, SPEC, SHA)
    assert chunk.repealed
    assert chunk.text == "[Repealed by Act No. 3 of 2006, 2nd Sch.;]\n(b) With offences under another Act."


def test_schedule_listing_repealed_laws_is_not_itself_repealed() -> None:
    pages = pages_of(["1. Short title", "Text one.", "SCHEDULE [s. 161]", "REPEALED LAWS", "The Old Act (Cap. 1)"])
    assert not parse_act(pages, SPEC, SHA)[1].repealed


def test_part_false_positive_in_body_is_text() -> None:
    pages = pages_of(["1. Courts", "A court established under this", "Part but in other respects competent."])
    (chunk,) = parse_act(pages, SPEC, SHA)
    assert chunk.part == ""
    assert chunk.text.endswith("this Part but in other respects competent.")


def test_duplicate_section_numbers_get_suffixed_ids() -> None:
    pages = pages_of(["1. First", "Text one.", "2. Second", "Text two."], ["2. Second again", "Text again."])
    chunks = parse_act(pages, SPEC, SHA)
    # A repeated number is not greater than the current one, so it stays as text unless the profile resets.
    assert [c.chunk_id for c in chunks] == ["sample-act-1", "sample-act-2"]
    schedule_pages = pages_of(["1. First", "Text one.", "SCHEDULE", "A", "SCHEDULE", "B"])
    ids = [c.chunk_id for c in parse_act(schedule_pages, SPEC, SHA)]
    assert ids == ["sample-act-1", "sample-act-sch1", "sample-act-sch1-2"]


def test_index_block_is_skipped_until_next_schedule() -> None:
    pages = pages_of(
        [
            "1. Short title",
            "This Act may be cited as X.",
            "INDEX TO THE SAMPLE ACT",
            "NOTE.- This index is not part of the Act.",
            "ABATEMENT of appeals 360",
            "THIRD SCHEDULE",
            "SPENT",
            "Spent",
        ]
    )
    chunks = parse_act(pages, SPEC, SHA)
    assert [c.section_num for c in chunks] == ["1", "Third Schedule"]
    assert "ABATEMENT" not in chunks[0].text
    assert chunks[1].repealed


def test_constitution_profile_tracks_chapters_and_articles() -> None:
    pages = pages_of(
        [
            "Constitution of Kenya Kenya",
            "GOD BLESS KENYA",
            "Chapter Four",
            "THE BILL OF RIGHTS",
            "Part 1 – General Provisions to the Bill of Rights",
            "19. Rights and fundamental freedoms",
            "(1) The Bill of Rights is an integral part of Kenya’s democratic state.",
            "Part 2 – Rights and fundamental freedoms",
            "20. Application of Bill of Rights",
            "(1) The Bill of Rights applies to all law.",
            "Chapter Five",
            "LAND AND ENVIRONMENT",
            "21. Implementation of rights",
            "It is a duty of the State to observe the Bill of Rights in this",
            "Chapter Fifteen applies;",
            "13",
        ]
    )
    chunks = parse_act(pages, CONSTITUTION, SHA, max_gap=25)
    assert [c.chunk_id for c in chunks] == [
        "constitution-of-kenya-19",
        "constitution-of-kenya-20",
        "constitution-of-kenya-21",
    ]
    assert {c.unit_type for c in chunks} == {"article"}
    assert chunks[0].chapter == "Chapter Four - THE BILL OF RIGHTS"
    assert chunks[1].part == "Part 2 - Rights and fundamental freedoms"
    assert chunks[2].chapter == "Chapter Five - LAND AND ENVIRONMENT"
    assert chunks[2].part == ""
    assert chunks[2].text.endswith("in this Chapter Fifteen applies;")
    assert "Kenya's democratic state" in chunks[0].text


def test_profile_lookup_defaults_for_unknown_acts() -> None:
    assert profile_for("employment-act") is DEFAULT_PROFILE
    assert profile_for("constitution-of-kenya").unit_type == "article"


@pytest.mark.parametrize(
    ("line", "noise"),
    [
        ("[Rev. 2012] CAP. 226", True),
        ("Employment Act (Cap. 226) Kenya", True),
        ("41. Notification and hearing ........................ 23", True),
        ("   ", True),
        ("(1) An employer shall pay wages.", False),
        ("41. Notification and hearing", False),
    ],
)
def test_is_noise(line: str, noise: bool) -> None:
    assert is_noise(line) is noise


@pytest.mark.parametrize(
    ("text", "repealed"),
    [
        ("[Repealed by Act No. 2 of 1970, s. 9.]", True),
        ("[Deleted by Act No. 20 of 2020 Sch.]", True),
        ("[Spent]", True),
        ("Repealed by Act No. 11 of 2014, s. 52.", True),
        ("SPENT\nSpent", True),
        ("[Repealed by Act No. 3 of 2006, 2nd Sch.;]", True),
        ("REPEALED LAWS", False),
        ("(1) Repealed provisions continue to apply to pending cases.", False),
        ("", False),
    ],
)
def test_is_repealed(text: str, repealed: bool) -> None:
    assert is_repealed(text) is repealed


def test_normalise_quotes_dashes_and_spaces() -> None:
    assert normalise("“a” ‘b’ c–d e f ﬁ g—h") == "\"a\" 'b' c-d e f fi g—h"


def test_parse_is_deterministic(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "a.pdf", SAMPLE_ACT_PAGES)
    first = [c.model_dump_json() for c in parse_act(extract_pages(pdf), SPEC, SHA)]
    second = [c.model_dump_json() for c in parse_act(extract_pages(pdf), SPEC, SHA)]
    assert first == second
