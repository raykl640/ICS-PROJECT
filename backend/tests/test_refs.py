import pytest

from backend.app.config import Settings
from backend.app.retrieval.refs import Ref, RefExtractor
from backend.app.retrieval.router import load_domains

EMP, LAND, CONST = "employment-act", "land-act", "constitution-of-kenya"


@pytest.fixture(scope="module")
def refs() -> RefExtractor:
    settings = Settings()
    return RefExtractor(settings.acts, load_domains(settings.domains_path, settings.acts).aliases)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("What does s. 41 say?", [Ref("section", "41", None)]),
        ("section 41 of the Employment Act", [Ref("section", "41", EMP)]),
        ("Article 47", [Ref("article", "47", CONST)]),
        ("Cap 226", []),
        ("s.41(2) and sec 45A", [Ref("section", "41", None), Ref("section", "45a", None)]),
        ("Employment Act, Section 10", [Ref("section", "10", EMP)]),
        ("section 45 of Cap 226", [Ref("section", "45", EMP)]),
        ("Article 47 and section 3 of the Land Act", [Ref("article", "47", CONST), Ref("section", "3", LAND)]),
        (
            "section 41 of the Employment Act or Article 41 of the Constitution",
            [Ref("section", "41", EMP), Ref("article", "41", CONST)],
        ),
        ("it's 41 days since I was fired", []),
        ("art. 49 rights", [Ref("article", "49", CONST)]),
        ("section 41 and section 41 again", [Ref("section", "41", None)]),
    ],
)
def test_extract_refs(refs: RefExtractor, query: str, expected: list[Ref]) -> None:
    assert refs.extract_refs(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Cap 226", [EMP]),
        ("CAP. 280 and the employment act", [LAND, EMP]),
        ("under the Land Act", [LAND]),
        ("my landlord", []),
        (
            "Landlord and Tenant (Shops, Hotels and Catering Establishments) Act",
            ["landlord-and-tenant-shops-hotels-and-catering-establishments-act"],
        ),
        ("the CPC says", ["criminal-procedure-code"]),
        ("Cap 999", []),
        ("is this constitutional", []),
        ("the Constitution and the constitution", [CONST]),
    ],
)
def test_act_mentions(refs: RefExtractor, query: str, expected: list[str]) -> None:
    assert refs.act_mentions(query) == expected
