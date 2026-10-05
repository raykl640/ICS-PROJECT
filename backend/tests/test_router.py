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
LR = "labour-relations-act"
PC = "penal-code"
EV = "evidence-act"
CIV = "civil-procedure-act"
SC = "small-claims-court-act"
LIM = "limitation-of-actions-act"
LRG = "land-registration-act"
M = "marriage-act"
MP = "matrimonial-property-act"
S = "law-of-succession-act"
TIP = "counter-trafficking-in-persons-act"
REF = "refugees-act"
PH = "public-health-act"
MH = "mental-health-act"
HIV = "hiv-and-aids-prevention-and-control-act"


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
    ("How do I get a title deed for my plot?", [L, LRG]),
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
    ("How much is cash bail for a traffic offence?", [CPC, T, PC, C]),
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
    # Acts added with the 25-Act corpus
    ("Our employer refuses to recognise the workers union", [LR, E, C]),
    ("Someone stole my phone at the market", [PC, C]),
    ("Can a WhatsApp screenshot be used as evidence?", [EV]),
    ("A customer owes me 50,000 shillings and refuses to pay", [SC]),
    ("Is it too late to sue for something that happened years ago?", [LIM, CIV]),
    ("How do I register my marriage?", [M]),
    ("My father died without a will, who inherits his land?", [S, L]),
    ("An agent took my passport and forced me to work without pay", [TIP]),
    ("How do I apply for refugee status?", [REF, C]),
    ("My neighbour's sewage flows into my compound", [PH]),
    ("Can my relative be admitted to a psychiatric hospital against her will?", [MH]),
    ("Can my employer disclose my HIV status?", [HIV, E, C]),
    ("What does the Matrimonial Property Act say about contribution?", [MP]),
    ("Cap 160 dependants", [S]),
    # Kiswahili fallbacks
    ("mwajiri wangu amenifuta kazi bila notisi", [E, C]),
    ("mwenye nyumba anataka kunifukuza", [R, C]),
    ("polisi walinipiga", [P, C]),
    ("ndoa yangu haijasajiliwa", [M]),
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
