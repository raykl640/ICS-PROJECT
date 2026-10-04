from backend.app.config import ActSpec, Settings
from backend.app.ingestion.report import ActReport, act_report, render_report, sequence_issues
from backend.app.models import LegalChunk

SPEC = ActSpec(name="Sample Act", year=2001, file="Sample Act.pdf")
LONG_TEXT = "Word " * 20


def chunk(num: str, text: str = LONG_TEXT, unit_type: str = "section", repealed: bool = False) -> LegalChunk:
    return LegalChunk.model_validate(
        {
            "chunk_id": f"sample-act-{num.lower().replace(' ', '-')}",
            "act": "Sample Act",
            "act_slug": "sample-act",
            "act_year": 2001,
            "unit_type": unit_type,
            "section_num": num,
            "section_title": "Title",
            "text": text,
            "page": 1,
            "repealed": repealed,
            "source_sha256": "0" * 64,
        }
    )


def test_sequence_without_issues_accepts_lettered_insertions() -> None:
    issues = sequence_issues(["40", "41", "41A", "41B", "42"])
    assert (issues.gaps, issues.duplicates, issues.out_of_order) == ([], [], [])


def test_sequence_gap_is_reported_with_missing_range() -> None:
    assert sequence_issues(["1", "2", "5", "6", "8"]).gaps == ["2 -> 5 (missing 3-4)", "6 -> 8 (missing 7)"]


def test_sequence_duplicates_and_out_of_order() -> None:
    issues = sequence_issues(["1", "2", "2", "41B", "41A", "42"])
    assert issues.duplicates == ["2"]
    assert issues.out_of_order == ["41B -> 41A"]


def test_act_report_counts_and_flags() -> None:
    chunks = [
        chunk("1"),
        chunk("2", "Too short"),
        chunk("3", "[Repealed by Act No. 1 of 2015.]", repealed=True),
        chunk("4", "Word " * 1501),
        chunk("5", "continues mid-sentence " * 10),
        chunk("7", ""),
        chunk("Schedule", "1. Form one " * 5, unit_type="schedule"),
    ]
    report = act_report(SPEC, chunks, Settings(chunk_min_words=15, chunk_max_words=1500))
    assert report.total == 7
    assert report.schedules == 1
    assert report.repealed == 1
    assert report.short == ["sample-act-2", "sample-act-7"]
    assert report.long == ["sample-act-4"]
    assert report.mid_sentence == ["sample-act-5"]
    assert report.empty == ["sample-act-7"]
    assert report.issues.gaps == ["5 -> 7 (missing 6)"]
    assert not report.failed


def test_empty_parse_fails() -> None:
    report = act_report(SPEC, [], Settings())
    assert report.failed


def test_render_report_lists_every_act_and_problem() -> None:
    reports = [
        act_report(SPEC, [chunk("1"), chunk("3")], Settings()),
        ActReport.empty_for(ActSpec(name="Other Act", year=2000, file="o.pdf"), note="needs_ocr"),
    ]
    text = render_report(reports)
    assert "| Sample Act | 2 |" in text
    assert "1 -> 3 (missing 2)" in text
    assert "Other Act" in text and "needs_ocr" in text
    assert "EMPTY PARSE" in text
