"""All tunable settings live here (CLAUDE.md hard rule 4). Override any field with env var HAKI_<FIELD>."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AnyHttpUrl, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SOURCES_PATH = DATA_DIR / "sources.yaml"

# Exact text from ARCHITECTURE.md §7.5; returned instead of calling the LLM when retrieval is not confident.
FALLBACK_MESSAGE = (
    "I cannot find a specific provision covering this in the current corpus. Please consult a qualified advocate."
)
DISCLAIMER = (
    "HakiAI provides legal information, not legal advice. Check the cited sources and consult a qualified advocate "
    "before acting on it."
)


class ActSpec(BaseModel):
    """One statute in the corpus and the PDF it is parsed from."""

    name: str
    year: int
    file: str
    url: str | None = None
    unit: Literal["Section", "Article"] = "Section"
    cap: str | None = None
    frbr_uri: str | None = None

    @property
    def slug(self) -> str:
        """Lowercase hyphenated Act name used in chunk ids."""
        return "-".join("".join(c if c.isalnum() else " " for c in self.name.lower()).split())


def load_acts(path: Path) -> list[ActSpec]:
    """Read the corpus list from sources.yaml, rejecting entries whose slug differs from the derived one."""
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))["acts"]
    acts = []
    for entry in entries:
        spec = ActSpec(name=entry["title"], **{k: v for k, v in entry.items() if k not in ("slug", "title")})
        if entry["slug"] != spec.slug:
            raise ValueError(f"{path.name}: slug {entry['slug']!r} != derived {spec.slug!r}")
        acts.append(spec)
    return acts


class Settings(BaseSettings):
    """Runtime configuration; every field can be overridden with env var HAKI_<FIELD>."""

    model_config = SettingsConfigDict(env_prefix="HAKI_", env_file=".env", extra="ignore")

    raw_pdf_dir: Path = DATA_DIR / "raw_pdfs"
    processed_dir: Path = DATA_DIR / "processed"
    index_dir: Path = DATA_DIR / "indexes"
    chunks_path: Path = DATA_DIR / "processed" / "chunks.json"
    feedback_path: Path = DATA_DIR / "feedback.jsonl"
    manifest_path: Path = DATA_DIR / "corpus_manifest.json"
    parse_report_path: Path = DATA_DIR / "processed" / "parse_report.md"
    acts: list[ActSpec] = Field(default_factory=lambda: load_acts(SOURCES_PATH))

    download_retries: int = Field(3, gt=0)
    download_timeout_s: float = Field(60.0, gt=0)
    download_user_agent: str = "HakiAI-corpus-fetcher/0.1 (academic research project)"
    ocr_enabled: bool = False
    ocr_min_page_chars: int = Field(25, ge=0)
    ocr_max_low_page_ratio: float = Field(0.2, ge=0.0, le=1.0)
    ocr_min_confidence: float = Field(60.0, ge=0.0, le=100.0)
    heading_max_gap: int = Field(10, gt=0)
    chunk_min_words: int = Field(15, gt=0)
    chunk_max_words: int = Field(1500, gt=0)

    dense_k: int = Field(20, gt=0)
    sparse_k: int = Field(20, gt=0)
    rrf_k: int = Field(60, gt=0)
    top_n: int = Field(20, gt=0)
    rerank_top: int = Field(5, gt=0)
    relevance_threshold: float = 0.0
    min_confident_chunks: int = Field(2, gt=0)
    embed_token_limit: int = 512
    embed_max_words: int = 400

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    translator_sw_en: str = "Helsinki-NLP/opus-mt-sw-en"
    translator_en_sw: str = "Helsinki-NLP/opus-mt-en-sw"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct-q4_K_M"
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    num_ctx: int = Field(8192, gt=0)
    num_predict: int = Field(1500, gt=0)
    ollama_timeout_s: float = Field(300.0, gt=0)

    max_question_chars: int = Field(1000, gt=0)
    session_ttl_s: int = Field(3600, gt=0)
    max_sessions: int = Field(200, gt=0)
    rate_limit_per_min: int = Field(10, gt=0)
    log_content: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(8000, gt=0, lt=65536)

    @model_validator(mode="after")
    def _check_consistency(self) -> "Settings":
        """Reject combinations that would break the retrieval funnel or the LLM context."""
        AnyHttpUrl(self.ollama_url)
        if self.rerank_top > self.top_n:
            raise ValueError("rerank_top must be <= top_n")
        if self.min_confident_chunks > self.rerank_top:
            raise ValueError("min_confident_chunks must be <= rerank_top")
        if self.num_predict >= self.num_ctx:
            raise ValueError("num_predict must be < num_ctx")
        return self

    def pdf_path(self, act: ActSpec) -> Path:
        """Location of an Act's source PDF."""
        return self.raw_pdf_dir / act.file


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, read once."""
    return Settings()
