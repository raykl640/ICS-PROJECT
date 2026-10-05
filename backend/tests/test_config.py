from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.config import DISCLAIMER, FALLBACK_MESSAGE, ActSpec, Settings, get_settings, load_acts


def test_defaults_match_spec() -> None:
    s = Settings()
    assert (s.dense_k, s.sparse_k, s.rrf_k, s.top_n, s.rerank_top) == (20, 20, 60, 20, 5)
    assert s.min_filtered_hits == 5
    assert s.domains_path.is_file()
    assert s.min_confident_chunks == 2
    assert s.relevance_threshold == -8.0
    assert (s.temperature, s.num_ctx, s.num_predict) == (0.1, 8192, 1500)
    assert s.embedding_dim == 384
    assert (s.session_ttl_s, s.max_sessions) == (3600, 200)
    assert s.max_question_chars == 1000
    assert s.rate_limit_per_min == 10
    assert s.log_content is False
    assert s.ollama_url.endswith(":11434")
    assert (s.embed_split_over_words, s.embed_window_words, s.embed_window_stride, s.embed_max_tokens) == (
        200,
        180,
        120,
        256,
    )
    assert (s.dense_index_dir.parent, s.sparse_index_dir.parent) == (s.index_dir, s.index_dir)
    assert (s.chunk_token_budget, s.prompt_safety_tokens, s.tokens_per_word) == (1200, 256, 1.4)
    assert s.prompt_budget == 8192 - 1500 - 256


def test_fallback_message_is_verbatim_from_architecture() -> None:
    assert FALLBACK_MESSAGE == (
        "I cannot find a specific provision covering this in the current corpus. Please consult a qualified advocate."
    )


def test_disclaimer_states_information_not_advice() -> None:
    assert "legal information, not legal advice" in DISCLAIMER


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


@pytest.mark.parametrize(
    ("env", "value", "field", "expected"),
    [
        ("HAKI_TOP_N", "7", "top_n", 7),
        ("HAKI_DENSE_K", "30", "dense_k", 30),
        ("HAKI_LOG_CONTENT", "true", "log_content", True),
        ("HAKI_OLLAMA_MODEL", "mistral:test", "ollama_model", "mistral:test"),
    ],
)
def test_env_override(monkeypatch: pytest.MonkeyPatch, env: str, value: str, field: str, expected: object) -> None:
    monkeypatch.setenv(env, value)
    assert getattr(Settings(), field) == expected


@pytest.mark.parametrize(
    ("env", "value"),
    [
        ("HAKI_TOP_N", "0"),
        ("HAKI_TEMPERATURE", "-0.1"),
        ("HAKI_RERANK_TOP", "21"),
        ("HAKI_MIN_CONFIDENT_CHUNKS", "6"),
        ("HAKI_NUM_PREDICT", "8192"),
        ("HAKI_NUM_PREDICT", "7936"),
        ("HAKI_MIN_CHUNK_TOKENS", "1201"),
        ("HAKI_MAX_QUESTION_CHARS", "abc"),
        ("HAKI_OLLAMA_URL", "localhost:11434"),
        ("HAKI_EMBED_WINDOW_STRIDE", "181"),
        ("HAKI_TOP_N", "41"),
        ("HAKI_EMBED_WINDOW_WORDS", "201"),
    ],
)
def test_invalid_settings_are_rejected(monkeypatch: pytest.MonkeyPatch, env: str, value: str) -> None:
    monkeypatch.setenv(env, value)
    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_actspec_slug() -> None:
    spec = ActSpec(name="Land Act", year=2012, file="Land Act.pdf")
    assert spec.slug == "land-act"
    assert isinstance(Path(spec.file), Path)


def test_sources_yaml_years_match_frbr_uris() -> None:
    for act in Settings().acts:
        assert act.frbr_uri is not None
        assert act.frbr_uri.split("/")[4] == str(act.year), act.name


def test_load_acts_rejects_a_slug_that_differs_from_the_title(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text("acts:\n  - {slug: wrong-slug, title: Land Act, year: 2012, file: Land Act.pdf}\n")
    with pytest.raises(ValueError, match="wrong-slug"):
        load_acts(path)
