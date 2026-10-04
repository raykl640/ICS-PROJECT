"""All tunable settings live here (CLAUDE.md hard rule 4). Override any field with env var HAKI_<FIELD>."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"


class ActSpec(BaseModel):
    name: str
    year: int
    file: str
    url: str | None = None
    unit: Literal["Section", "Article"] = "Section"

    @property
    def slug(self) -> str:
        return "-".join("".join(c if c.isalnum() else " " for c in self.name.lower()).split())


# Years are to be confirmed against the PDFs during M1 (see docs/PROGRESS.md).
ACTS: tuple[ActSpec, ...] = (
    ActSpec(name="Constitution of Kenya", year=2010, file="Constitution of Kenya.pdf", unit="Article"),
    ActSpec(name="Employment Act", year=2007, file="Employment Act.pdf"),
    ActSpec(
        name="Landlord and Tenant (Shops, Hotels and Catering Establishments) Act",
        year=1965,
        file="Landlord and Tenant (Shops Hotels and Catering Establishments) Act.pdf",
    ),
    ActSpec(name="Rent Restriction Act", year=1959, file="Rent Restriction Act.pdf"),
    ActSpec(name="Land Act", year=2012, file="Land Act.pdf"),
    ActSpec(name="Consumer Protection Act", year=2012, file="Consumer Protection Act.pdf"),
    ActSpec(name="National Police Service Act", year=2011, file="National Police Service Act.pdf"),
    ActSpec(name="Criminal Procedure Code", year=1930, file="Criminal Procedure Code.pdf"),
    ActSpec(name="Traffic Act", year=1953, file="Traffic Act.pdf"),
    ActSpec(name="Legal Aid Act", year=2016, file="Legal Aid Act.pdf"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HAKI_", env_file=".env", extra="ignore")

    raw_pdf_dir: Path = DATA_DIR / "raw_pdfs"
    processed_dir: Path = DATA_DIR / "processed"
    index_dir: Path = DATA_DIR / "indexes"
    chunks_path: Path = DATA_DIR / "processed" / "chunks.json"
    feedback_path: Path = DATA_DIR / "feedback.jsonl"
    acts: list[ActSpec] = Field(default_factory=lambda: list(ACTS))

    rrf_k: int = 60
    top_n: int = 20
    rerank_top: int = 5
    relevance_threshold: float = 0.0
    min_confident_chunks: int = 2
    embed_token_limit: int = 512
    embed_max_words: int = 400

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    translator_sw_en: str = "Helsinki-NLP/opus-mt-sw-en"
    translator_en_sw: str = "Helsinki-NLP/opus-mt-en-sw"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct-q4_K_M"
    temperature: float = 0.1
    ollama_timeout_s: float = 300.0

    session_ttl_s: int = 3600
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    def pdf_path(self, act: ActSpec) -> Path:
        return self.raw_pdf_dir / act.file


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
