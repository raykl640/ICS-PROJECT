from pathlib import Path

from backend.app.config import ActSpec, Settings, get_settings


def test_defaults_match_spec() -> None:
    s = Settings()
    assert s.rrf_k == 60
    assert s.top_n == 20
    assert s.rerank_top == 5
    assert s.min_confident_chunks == 2
    assert s.relevance_threshold == 0.0
    assert s.temperature == 0.1
    assert s.embedding_dim == 384
    assert s.session_ttl_s == 3600
    assert s.ollama_url.endswith(":11434")


def test_corpus_has_ten_acts_with_unique_files() -> None:
    acts = Settings().acts
    assert len(acts) == 10
    assert len({a.file for a in acts}) == 10
    assert len({a.name for a in acts}) == 10


def test_constitution_uses_articles() -> None:
    units = {a.name: a.unit for a in Settings().acts}
    assert units["Constitution of Kenya"] == "Article"
    assert units["Employment Act"] == "Section"


def test_act_pdf_path_is_under_raw_pdf_dir() -> None:
    s = Settings()
    act = s.acts[0]
    assert s.pdf_path(act) == s.raw_pdf_dir / act.file
    assert s.raw_pdf_dir.name == "raw_pdfs"


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("HAKI_TOP_N", "7")
    assert Settings().top_n == 7


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_actspec_slug() -> None:
    spec = ActSpec(name="Land Act", year=2012, file="Land Act.pdf")
    assert spec.slug == "land-act"
    assert isinstance(Path(spec.file), Path)
