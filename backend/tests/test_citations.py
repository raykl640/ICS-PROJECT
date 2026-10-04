"""Citation extraction (real Act names/aliases from config, synthetic Acts for verification) and verification."""

import pytest

from backend.app.generation.citations import Citation, check_citations, extract_citations
from backend.app.models import LegalChunk
from backend.app.retrieval.refs import RefExtractor
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, TENANCY, corpus
from backend.tests.fake_pipeline import ACTS, TABLE

SAMPLE_REFS = RefExtractor(ACTS, TABLE.aliases)
EMP = "employment-act"
CONST = "constitution-of-kenya"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(Employment Act, s. 41)", [Citation("section", "41", EMP)]),
        ("Under the Employment Act 2007, section 41(2)(a) applies.", [Citation("section", "41", EMP)]),
        ("See Cap 226, s.45.", [Citation("section", "45", EMP)]),
        (
            "Section 41 of the Employment Act and Article 41 of the Constitution",
            [
                Citation("section", "41", EMP),
                Citation("article", "41", CONST),
            ],
        ),
        ("(Constitution of Kenya, Art. 27(4))", [Citation("article", "27", CONST)]),
        ("Employment Act, sections 41 to 43", [Citation("section", n, EMP) for n in ("41", "42", "43")]),
        ("Employment Act, ss. 35-36", [Citation("section", n, EMP) for n in ("35", "36")]),
        ("Employment Act, sections 41, 43 and 45", [Citation("section", n, EMP) for n in ("41", "43", "45")]),
        (
            "Employment Act, sections 41(2) and 43(1)(b)",
            [Citation("section", "41", EMP), Citation("section", "43", EMP)],
        ),
        ("Articles 27 and 41", [Citation("article", "27", CONST), Citation("article", "41", CONST)]),
        ("Rent Restriction Act, s. 14A", [Citation("section", "14a", "rent-restriction-act")]),
        ("Section 5 says so.", [Citation("section", "5", None)]),
        (
            "s. 45 of the Rent Restriction Act and s. 3 of the Land Act",
            [Citation("section", "45", "rent-restriction-act"), Citation("section", "3", "land-act")],
        ),
        ("(Employment Act, s. 41) ... (Employment Act, s. 41)", [Citation("section", "41", EMP)]),
        ("The Act protects you; the section number is in the text.", []),
        ("Employment Act, sections 10 to 90", [Citation("section", "10", EMP), Citation("section", "90", EMP)]),
    ],
)
def test_extract_citations_with_the_real_alias_table(text: str, expected: list[Citation]) -> None:
    assert extract_citations(text) == expected


def test_act_year_and_cap_aliases_resolve_to_the_same_act() -> None:
    assert extract_citations("Employment Act 2007, s. 41") == extract_citations("Cap 226, s. 41")


def _given() -> list[LegalChunk]:
    by_id = {c.chunk_id: c for c in corpus()}
    return [by_id[f"{EMPLOYMENT}-4"], by_id[f"{EMPLOYMENT}-3"], by_id[f"{CONSTITUTION}-41"]]


def test_verify_separates_given_sections_from_hallucinated_ones() -> None:
    answer = (
        "Your dismissal may be unfair (Sample Employment Act, s. 4). Notice is required (Sample Employment Act, s. 3). "
        "You can sue within 90 days (Sample Employment Act, s. 99). Fair labour practices apply (Article 41)."
    )
    check = check_citations(answer, _given(), SAMPLE_REFS)
    assert check.verified == [
        "Sample Employment Act s. 4",
        "Sample Employment Act s. 3",
        "Sample Constitution Article 41",
    ]
    assert check.unmatched == ["Sample Employment Act s. 99"]


def test_section_cited_from_the_wrong_act_is_unmatched() -> None:
    check = check_citations("(Sample Tenancy Act, s. 4)", _given(), SAMPLE_REFS)
    assert check.unmatched == ["Sample Tenancy Act s. 4"]
    assert TENANCY not in {c.act_slug for c in _given()}


def test_unbound_section_is_verified_only_if_some_given_chunk_has_it() -> None:
    check = check_citations("Read section 3 and section 77.", _given(), SAMPLE_REFS)
    assert check.verified == ["(no Act named) s. 3"]
    assert check.unmatched == ["(no Act named) s. 77"]


def test_answer_without_citations_gives_an_empty_check() -> None:
    check = check_citations("No provision covers this.", _given(), SAMPLE_REFS)
    assert (check.verified, check.unmatched) == ([], [])
