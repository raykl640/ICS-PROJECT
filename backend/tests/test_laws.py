"""Laws browser: cross-reference resolution, refs.json, snippet offsets, catalog endpoints, search, recent reads."""

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.ingestion.build_index import build_indexes
from backend.app.laws.catalog import make_snippet, match_spans
from backend.app.laws.xrefs import build_cross_refs, load_cross_refs
from backend.app.retrieval.meta import REBUILD_COMMAND, IndexMismatchError
from backend.app.retrieval.refs import RefExtractor
from backend.app.retrieval.store import ChunkStore
from backend.tests.api_support import APP_HEADERS, TickingClock, make_app
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, TENANCY, make_chunk
from backend.tests.fake_pipeline import ACTS, STORE, TABLE
from backend.tests.fakes import FakeEmbedder, FakeLLM

EXTRACTOR = RefExtractor(ACTS, TABLE.aliases)
PW = "a long enough password"


def _refs(*chunks: Any) -> dict[str, list[tuple[str, str | None]]]:
    built = build_cross_refs(ChunkStore(chunks), EXTRACTOR)
    return {cid: [(link.label, link.chunk_id) for link in links] for cid, links in built.out.items()}


# --- cross-references -----------------------------------------------------------------------------------------


def test_same_act_and_named_act_refs_resolve() -> None:
    refs = _refs(
        make_chunk(EMPLOYMENT, "1", "A", "See section 2 and section 41 of the Sample Tenancy Act and Article 27."),
        make_chunk(EMPLOYMENT, "2", "B", "Text."),
        make_chunk(TENANCY, "41", "C", "Text."),
        make_chunk(CONSTITUTION, "27", "D", "Text.", unit_type="article"),
    )
    assert refs[f"{EMPLOYMENT}-1"] == [
        ("Section 2", f"{EMPLOYMENT}-2"),
        ("Sample Tenancy Act, section 41", f"{TENANCY}-41"),
        ("Sample Constitution, article 27", f"{CONSTITUTION}-27"),
    ]


def test_bare_section_never_pulls_an_article() -> None:
    refs = _refs(
        make_chunk(CONSTITUTION, "1", "A", "As provided in section 41, and in Article 41.", unit_type="article"),
        make_chunk(CONSTITUTION, "41", "B", "Text.", unit_type="article"),
    )
    assert refs[f"{CONSTITUTION}-1"] == [("Article 41", f"{CONSTITUTION}-41")]


def test_repealed_missing_foreign_and_self_refs() -> None:
    refs = _refs(
        make_chunk(EMPLOYMENT, "1", "A", "Under section 7, section 99, section 3 of the Penal Code and section 1."),
        make_chunk(EMPLOYMENT, "7", "Gone", "[Repealed]", repealed=True),
    )
    assert refs[f"{EMPLOYMENT}-1"] == [("Section 7", None), ("Section 99", None)]


def test_of_this_act_and_subsections_bind_to_the_own_act() -> None:
    refs = _refs(
        make_chunk(TENANCY, "1", "A", "Under section 2(1)(a) of this Act, or section 2 of the Act."),
        make_chunk(TENANCY, "2", "B", "Text."),
    )
    assert refs[f"{TENANCY}-1"] == [("Section 2", f"{TENANCY}-2")]


def test_cited_by_is_the_inverse_in_document_order() -> None:
    built = build_cross_refs(STORE, EXTRACTOR)
    assert built.cited_by[f"{EMPLOYMENT}-4"] == [f"{EMPLOYMENT}-8"]
    assert ("Section 6", None) in [(link.label, link.chunk_id) for link in built.out[f"{TENANCY}-41"]]
    assert built.resolved == 3 and built.unresolved == 1


def test_build_index_writes_refs_json_tied_to_the_corpus(tmp_path: Path) -> None:
    settings = Settings(acts=ACTS, chunks_path=tmp_path / "chunks.json", index_dir=tmp_path / "indexes")
    STORE.save(settings.chunks_path)
    stats = build_indexes(settings, FakeEmbedder(), EXTRACTOR)
    assert (stats.refs_resolved, stats.refs_unresolved, stats.refs_citing) == (3, 1, 2)
    assert load_cross_refs(settings.refs_path, STORE.corpus_hash).resolved == 3
    with pytest.raises(IndexMismatchError, match="stale"):
        load_cross_refs(settings.refs_path, "0" * 64)
    settings.refs_path.unlink()
    with pytest.raises(IndexMismatchError, match=REBUILD_COMMAND):
        load_cross_refs(settings.refs_path, STORE.corpus_hash)


# --- snippets -------------------------------------------------------------------------------------------------


def test_snippet_marks_are_valid_code_point_offsets_with_unicode() -> None:
    text = "Café ñandú 🙂 " * 30 + "the employer dismissed the employee " + "😀 ü " * 40
    snippet = make_snippet(text, match_spans(text, "employers employees dismissal"), 120)
    assert snippet.text.startswith("…") and snippet.text.endswith("…")
    assert len(snippet.text) <= 122
    assert [snippet.text[s:e] for s, e in snippet.marks] == ["employer", "dismissed", "employee"]


def test_snippet_without_matches_starts_at_the_beginning() -> None:
    snippet = make_snippet("Short text.", [], 240)
    assert snippet.text == "Short text." and snippet.marks == []


def test_snippet_picks_the_densest_window() -> None:
    text = "wages once. " + "filler " * 60 + "wages and wages and wages."
    snippet = make_snippet(text, match_spans(text, "wages"), 60)
    assert len(snippet.marks) == 3


# --- endpoints ------------------------------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return make_app(tmp_path, FakeLLM(), wall_clock=TickingClock(), app_db_path=tmp_path / "app.db", reads_max=3)


@pytest.fixture
def c(app: FastAPI) -> Any:
    with TestClient(app, raise_server_exceptions=False, headers=APP_HEADERS) as client:
        yield client


def test_act_list_and_toc_order(c: TestClient) -> None:
    acts = c.get("/api/laws").json()
    assert [a["slug"] for a in acts] == [CONSTITUTION, EMPLOYMENT, TENANCY]
    assert acts[1] == {
        "slug": EMPLOYMENT,
        "name": "Sample Employment Act",
        "year": 2000,
        "unit": "Section",
        "sections": 9,
        "repealed": 1,
    }
    toc = c.get(f"/api/laws/{EMPLOYMENT}").json()
    items = [i for g in toc["groups"] for i in g["items"]]
    assert [i["num"] for i in items] == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "41"]
    assert [i["num"] for i in items if i["repealed"]] == ["7"]


def test_section_view_is_verbatim_with_neighbours_and_refs(c: TestClient) -> None:
    view = c.get(f"/api/laws/sections/{EMPLOYMENT}-8").json()
    stored = STORE.get([f"{EMPLOYMENT}-8"])[0]
    assert view["chunk"]["text"] == stored.text
    assert (view["prev"], view["next"]) == (f"{EMPLOYMENT}-7", f"{EMPLOYMENT}-9")
    assert {"label": "Section 4", "chunk_id": f"{EMPLOYMENT}-4"} in view["refs_out"]
    cited = c.get(f"/api/laws/sections/{EMPLOYMENT}-4").json()["refs_in"]
    assert cited == [{"label": "Sample Employment Act, section 8", "chunk_id": f"{EMPLOYMENT}-8"}]
    first = c.get(f"/api/laws/sections/{EMPLOYMENT}-1").json()
    assert first["prev"] is None


@pytest.mark.parametrize("path", ["/api/laws/no-such-act", "/api/laws/sections/no-such-section"])
def test_unknown_act_or_section_is_404(c: TestClient, path: str) -> None:
    r = c.get(path)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_search_ranks_and_filters(c: TestClient) -> None:
    hits = c.get("/api/search", params={"q": "landlord evict tenant"}).json()["hits"]
    assert hits[0]["chunk_id"] == f"{TENANCY}-3"
    hit = hits[0]
    assert [hit["snippet"][s:e].lower() for s, e in hit["marks"]] == ["landlord", "evict", "tenant"]
    only = c.get("/api/search", params={"q": "leave", "acts": CONSTITUTION}).json()["hits"]
    assert only == []
    assert c.get("/api/search", params={"q": "*:* OR ("}).status_code == 200
    assert c.get("/api/search", params={"q": "x" * 5000}).status_code == 422
    capped = c.get("/api/search", params={"q": "the", "limit": 1}).json()["hits"]
    assert len(capped) <= 1


def test_recent_reads_need_sign_in_and_respect_history(c: TestClient) -> None:
    assert c.post("/api/reads", json={"chunk_id": f"{EMPLOYMENT}-4"}).status_code == 401
    assert c.post("/api/auth/register", json={"username": "wanjiru", "password": PW}).status_code == 200
    for num in ["1", "2", "3", "1", "4"]:
        assert c.post("/api/reads", json={"chunk_id": f"{EMPLOYMENT}-{num}"}).json() == {"saved": True}
    reads = [r["chunk_id"] for r in c.get("/api/reads").json()]
    assert reads == [f"{EMPLOYMENT}-4", f"{EMPLOYMENT}-1", f"{EMPLOYMENT}-3"]
    assert c.post("/api/reads", json={"chunk_id": "nope"}).status_code == 404
    assert c.get("/api/account/export").json()["library"]["reads"][0]["chunk_id"] == f"{EMPLOYMENT}-4"
    c.put("/api/account/prefs", json={"save_history": False, "auto_lock_minutes": 15})
    assert c.post("/api/reads", json={"chunk_id": f"{EMPLOYMENT}-5"}).json() == {"saved": False}
