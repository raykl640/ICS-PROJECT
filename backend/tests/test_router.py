from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.retrieval.router import Router, load_domains, stem_words

C = "constitution-of-kenya"
E = "employment-act"
LT = "landlord-and-tenant-shops-hotels-and-catering-establishments-act"
R = "rent-restriction-act"
L = "land-act"
CP = "consumer-protection-act"
P = "national-police-service-act"
CPC = "criminal-procedure-code"
T = "traffic-act"
LA = "legal-aid-act"


@pytest.fixture(scope="module")
def router() -> Router:
    return Router.from_settings(Settings())


CASES: list[tuple[str, list[str] | None]] = [
    # employment (+ Constitution as rights co-domain)
    ("My employer fired me without notice", [E, C]),
    ("I was dismissed from my job after five years, what are my rights?", [E, C]),
    ("My boss has not paid my salary for three months", [E, C]),
    ("Am I entitled to maternity leave?", [E, C]),
    ("I was declared redundant and got no severance", [E, C]),
    # housing
    ("My landlord wants to evict me from my house", [R, LT, C]),
    ("The landlord increased the rent of my shop", [LT, R, C]),
    ("My landlord locked my apartment because of rent arrears", [R, LT, C]),
    ("My tenant has refused to pay rent for my commercial building", [LT, R, C]),
    # land, consumer, traffic, legal aid (no co-domain)
    ("How do I get a title deed for my plot?", [L]),
    ("The government took my land for a road without compensation", [L]),
    ("I bought a phone that stopped working and the seller refused a refund", [CP]),
    ("The goods I received were counterfeit", [CP]),
    ("What is the fine for speeding?", [T]),
    ("My driving licence was confiscated", [T]),
    ("The matatu I was travelling in had an accident and the driver ran away", [T]),
    ("Can I get a free lawyer?", [LA]),
    ("I cannot afford an advocate for my case", [LA]),
    # police and criminal procedure
    ("Police officers beat me at the police station", [P, C]),
    ("I was arrested and held for three days without being taken to court", [CPC, C]),
    ("How much is cash bail for a traffic offence?", [CPC, T, C]),
    ("I was charged with drunk driving", [T, CPC, C]),
    # multi-Act and rights-only
    ("My employer fired me and the police arrested me when I protested", [E, C, P, CPC]),
    ("Can my employer read my messages? I think my privacy was violated", [C, E]),
    ("Is it legal to discriminate against me because of my religion?", [C]),
    # explicit mentions override keywords
    ("What does section 41 of the Employment Act say?", [E]),
    ("Explain Article 47", [C]),
    ("Under the Land Act can my neighbour block my access road?", [L]),
    ("Cap 226 termination notice", [E]),
    ("Does the Constitution protect tenants from eviction?", [C]),
    ("Compare section 41 of the Employment Act with Article 41 of the Constitution", [E, C]),
    # Kiswahili fallbacks
    ("mwajiri wangu amenifuta kazi bila notisi", [E, C]),
    ("mwenye nyumba anataka kunifukuza", [R, C]),
    ("polisi walinipiga", [P, C]),
    # no match -> full corpus
    ("What is the weather like today?", None),
    ("Tell me a joke", None),
    ("section 12", None),
    ("", None),
]


@pytest.mark.parametrize(("question", "expected"), CASES)
def test_route(router: Router, question: str, expected: list[str] | None) -> None:
    assert router.route(question) == expected


def test_at_least_thirty_sample_questions() -> None:
    assert len(CASES) >= 30


def test_every_act_has_at_least_25_distinct_terms() -> None:
    settings = Settings()
    table = load_domains(settings.domains_path, settings.acts)
    assert set(table.terms) == {a.slug for a in settings.acts}
    for slug, terms in table.terms.items():
        assert len(terms) >= 25, slug


def test_stemming_matches_inflections() -> None:
    assert stem_words("Evicted evictions EVICT") == ["evict", "evict", "evict"]


def test_unknown_slug_in_table_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "domains.yaml"
    path.write_text("co_domain: x\nco_domain_for: []\nacts:\n  no-such-act: {aliases: [], terms: [a]}\n")
    with pytest.raises(ValueError, match="no-such-act"):
        load_domains(path, Settings().acts)
