"""Shared data types passed between pipeline stages and the API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.config import get_settings

Language = Literal["auto", "en", "sw"]
UserLanguage = Literal["en", "sw"]
UnitType = Literal["section", "article", "schedule"]


class LegalChunk(BaseModel):
    """One statutory unit (section, article or schedule) with its source metadata."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    act: str
    act_slug: str
    act_year: int
    unit_type: UnitType
    chapter: str = ""
    part: str = ""
    section_num: str
    section_title: str
    text: str
    page: int = Field(ge=1)
    repealed: bool = False
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RetrievedChunk(BaseModel):
    """A chunk carried through retrieval with its rank and score at each stage."""

    chunk: LegalChunk
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rrf_score: float
    rerank_score: float | None = None
    truncated: bool = False


class ParsedResponse(BaseModel):
    """LLM answer split into its three headed sections; missing sections are empty (and make format_ok False)."""

    rights: str = ""
    steps: str = ""
    letter: str = ""
    format_ok: bool = True


class CitationCheck(BaseModel):
    """Citations found in an answer, split by whether they match a retrieved chunk."""

    verified: list[str] = Field(default_factory=list)
    unmatched: list[str] = Field(default_factory=list)


class SessionData(BaseModel):
    """Server-side state for one question, from retrieval through generation."""

    question: str
    question_en: str
    lang: UserLanguage
    chunks: list[RetrievedChunk]
    fallback: bool
    answer_en: str = ""
    parsed: ParsedResponse | None = None
    parsed_user: ParsedResponse | None = None
    done: bool = False


class QueryRequest(BaseModel):
    """Body of POST /api/query."""

    question: str = Field(min_length=1, pattern=r"\S")
    language: Language = "auto"

    @field_validator("question")
    @classmethod
    def _within_length_limit(cls, question: str) -> str:
        """Reject questions longer than the configured maximum."""
        limit = get_settings().max_question_chars
        if len(question) > limit:
            raise ValueError(f"question longer than {limit} characters")
        return question


class QueryResponse(BaseModel):
    """Response of POST /api/query."""

    session_id: str
    fallback: bool


class FeedbackIn(BaseModel):
    """Body of POST /api/feedback."""

    session_id: str
    rating: Literal["up", "down"]


class ErrorBody(BaseModel):
    """Payload of every non-2xx response, wrapped as {"error": ErrorBody}."""

    code: str
    message: str
