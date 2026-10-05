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
DOMAINS_PATH = ROOT_DIR / "backend" / "app" / "retrieval" / "domains.yaml"
SCOPE_PATH = ROOT_DIR / "backend" / "app" / "retrieval" / "scope.yaml"
LANG_DIR = ROOT_DIR / "backend" / "app" / "lang"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
EVAL_DIR = ROOT_DIR / "eval"

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
    domains_path: Path = DOMAINS_PATH
    scope_path: Path = SCOPE_PATH
    glossary_path: Path = LANG_DIR / "glossary.json"
    ui_strings_path: Path = LANG_DIR / "ui_strings.json"
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
    min_filtered_hits: int = Field(5, gt=0)
    top_n: int = Field(20, gt=0)
    rerank_top: int = Field(5, gt=0)
    relevance_threshold: float = -2.0
    min_confident_chunks: int = Field(2, gt=0)
    # Semantic scope check (retrieval/scope.py): a question whose margin reaches scope_margin is answered even when the
    # cross-encoder is not confident; the fallback is used only when both say no (DEVIATIONS D21).
    scope_margin: float = 0.06
    scope_neighbours: int = Field(3, gt=0)
    embed_split_over_words: int = Field(200, gt=0)
    embed_window_words: int = Field(180, gt=0)
    embed_window_stride: int = Field(120, gt=0)
    embed_max_tokens: int = Field(256, gt=0)
    embed_batch_size: int = Field(32, gt=0)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_max_length: int = Field(512, gt=0)
    reranker_batch_size: int = Field(8, gt=0)
    # opus-mt-sw-en does not exist on the Hugging Face Hub; swc (Congo Swahili) is the closest sw→en Marian model (D15).
    translator_sw_en: str = "Helsinki-NLP/opus-mt-swc-en"
    translator_en_sw: str = "Helsinki-NLP/opus-mt-en-sw"
    translate_max_tokens: int = Field(350, gt=0)
    translate_batch_size: int = Field(8, gt=0)
    translate_num_beams: int = Field(4, gt=0)
    translate_max_new_tokens: int = Field(512, gt=0)
    lang_min_detect_chars: int = Field(20, ge=0)
    lang_min_detect_prob: float = Field(0.7, ge=0.0, le=1.0)

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct-q4_K_M"
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    num_ctx: int = Field(8192, gt=0)
    num_predict: int = Field(1500, gt=0)
    ollama_connect_timeout_s: float = Field(5.0, gt=0)
    ollama_read_timeout_s: float = Field(300.0, gt=0)
    ollama_health_timeout_s: float = Field(3.0, gt=0)
    ollama_keep_alive: str = "30m"
    prompt_safety_tokens: int = Field(256, ge=0)
    chunk_token_budget: int = Field(1200, gt=0)
    min_chunk_tokens: int = Field(40, gt=0)
    tokens_per_word: float = Field(1.4, gt=0)

    max_question_chars: int = Field(1000, gt=0)
    max_comment_chars: int = Field(500, ge=0)
    max_body_bytes: int = Field(16_384, gt=0)
    session_ttl_s: int = Field(3600, gt=0)
    session_purge_interval_s: float = Field(60.0, gt=0)
    max_sessions: int = Field(200, gt=0)
    max_queue: int = Field(8, ge=0)
    busy_retry_after_s: int = Field(30, gt=0)
    sse_ping_s: float = Field(15.0, gt=0)
    rate_limit_per_min: int = Field(10, gt=0)
    log_content: bool = False
    debug_scores: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(8000, gt=0, lt=65536)
    frontend_dist: Path = FRONTEND_DIST
    # CORS is only for the Vite dev server; the production build is served same-origin.
    dev_mode: bool = False
    cors_dev_origin: str = "http://localhost:5173"
    # Synthetic corpus + fake models instead of indexes, MiniLM, Marian and Ollama (frontend development; devstack.py).
    fake_backends: bool = False

    # Local accounts (M13, DESIGN_V2 "Accounts and encrypted store"). Tests use cheap argon2 parameters.
    app_db_path: Path = DATA_DIR / "app.db"
    argon2_time_cost: int = Field(3, gt=0)
    argon2_memory_kib: int = Field(65_536, ge=8)
    argon2_parallelism: int = Field(2, gt=0)
    auth_session_ttl_s: int = Field(43_200, gt=0)
    auto_lock_s: int = Field(900, gt=0)
    login_max_attempts: int = Field(5, gt=0)
    login_lockout_s: int = Field(30, gt=0)
    login_lockout_max_s: int = Field(3600, gt=0)
    password_min_chars: int = Field(10, ge=8)
    username_max_chars: int = Field(32, gt=2)
    profile_field_max_chars: int = Field(200, gt=0)
    auth_rate_limit_per_min: int = Field(20, gt=0)
    # Host header allow-list (DNS-rebinding defence for the localhost server); hostnames, any port.
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "[::1]"])

    # Library (M14): saved conversations, background answers, follow-ups, letters, matters, bookmarks, notes.
    background_runs: bool = True
    followup_context_turns: int = Field(1, ge=0)
    letter_versions_max: int = Field(20, gt=0)
    library_page_size: int = Field(50, gt=0)
    title_max_chars: int = Field(80, gt=0)
    matter_name_max_chars: int = Field(120, gt=0)
    letter_max_chars: int = Field(12_000, gt=0)
    note_max_chars: int = Field(4_000, gt=0)
    # Undelivered turn_done/turn_failed events kept per sign-in until GET /api/events connects.
    events_backlog: int = Field(20, gt=0)

    # Evaluation harness (eval/, M9). Input and result files are fixed names under eval_dir (see properties below).
    eval_dir: Path = EVAL_DIR
    eval_bootstrap_resamples: int = Field(10_000, gt=0)
    eval_seed: int = 0
    eval_raters: int = Field(3, ge=2)

    @model_validator(mode="after")
    def _check_consistency(self) -> "Settings":
        """Reject combinations that would break the retrieval funnel or the LLM context."""
        AnyHttpUrl(self.ollama_url)
        AnyHttpUrl(self.cors_dev_origin)
        if self.top_n > self.dense_k + self.sparse_k:
            raise ValueError("top_n must be <= dense_k + sparse_k")
        if self.rerank_top > self.top_n:
            raise ValueError("rerank_top must be <= top_n")
        if self.min_confident_chunks > self.rerank_top:
            raise ValueError("min_confident_chunks must be <= rerank_top")
        if self.num_predict + self.prompt_safety_tokens >= self.num_ctx:
            raise ValueError("num_predict + prompt_safety_tokens must be < num_ctx")
        if self.min_chunk_tokens > self.chunk_token_budget:
            raise ValueError("min_chunk_tokens must be <= chunk_token_budget")
        if not self.embed_window_stride <= self.embed_window_words <= self.embed_split_over_words:
            raise ValueError("need embed_window_stride <= embed_window_words <= embed_split_over_words")
        if self.login_lockout_s > self.login_lockout_max_s:
            raise ValueError("login_lockout_s must be <= login_lockout_max_s")
        if not self.allowed_hosts:
            raise ValueError("allowed_hosts must not be empty")
        return self

    @property
    def dense_index_dir(self) -> Path:
        """FAISS index, window id map and meta.json."""
        return self.index_dir / "dense"

    @property
    def sparse_index_dir(self) -> Path:
        """Whoosh BM25 index and meta.json."""
        return self.index_dir / "sparse"

    @property
    def prompt_budget(self) -> int:
        """Estimated tokens the whole prompt may use: num_ctx minus the answer and a safety margin."""
        return self.num_ctx - self.num_predict - self.prompt_safety_tokens

    @property
    def ground_truth_path(self) -> Path:
        """Human-written retrieval answer key (never generated)."""
        return self.eval_dir / "ground_truth.json"

    @property
    def out_of_corpus_path(self) -> Path:
        """Out-of-scope questions for the null-threshold sweep."""
        return self.eval_dir / "out_of_corpus.json"

    @property
    def functional_queries_path(self) -> Path:
        """End-to-end questions (no answers) for run_functional."""
        return self.eval_dir / "queries_functional.json"

    @property
    def eval_results_dir(self) -> Path:
        """JSON/markdown outputs of every evaluation step."""
        return self.eval_dir / "results"

    @property
    def ratings_dir(self) -> Path:
        """One rating sheet CSV per human rater."""
        return self.eval_dir / "ratings"

    @property
    def usability_responses_path(self) -> Path:
        """Survey answers entered by hand from eval/usability_survey.md."""
        return self.eval_dir / "usability_responses.csv"

    @property
    def eval_report_path(self) -> Path:
        """Assembled evaluation report."""
        return self.eval_dir / "report.md"

    def pdf_path(self, act: ActSpec) -> Path:
        """Location of an Act's source PDF."""
        return self.raw_pdf_dir / act.file


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, read once."""
    return Settings()
