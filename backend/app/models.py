"""Shared data types passed between pipeline stages and the API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.config import get_settings

Language = Literal["auto", "en", "sw"]
UserLanguage = Literal["en", "sw"]
UnitType = Literal["section", "article", "schedule"]
SessionStatus = Literal["pending", "running", "done", "aborted", "error"]


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
    """Server-side state for one question, from retrieval through generation (in memory only, never logged).

    status: pending (retrieved) -> running (queued or generating) -> done | aborted (client left) | error.
    Null (fallback) sessions start as done.
    """

    question: str
    question_en: str
    lang: UserLanguage
    chunks: list[RetrievedChunk]
    fallback: bool
    acts: list[str] = Field(default_factory=list)
    status: SessionStatus = "pending"
    answer_en: str = ""
    parsed: ParsedResponse | None = None
    parsed_user: ParsedResponse | None = None
    citation_check: CitationCheck | None = None
    untranslated: list[str] = Field(default_factory=list)
    feedback_given: bool = False


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
    """Response of POST /api/query: acts are the routed Act slugs ([] = whole corpus), language the resolved one."""

    session_id: str
    null_response: bool
    acts: list[str]
    language: UserLanguage


class SourceChunk(BaseModel):
    """One retrieved chunk as shown in the Sources panel (verbatim text); rerank_score only in debug mode."""

    chunk_id: str
    act: str
    unit_type: UnitType
    section_num: str
    section_title: str
    part: str
    page: int
    text: str
    truncated: bool
    rank: int
    rerank_score: float | None = None


class SourcesResponse(BaseModel):
    """Response of GET /api/sources/{session_id}."""

    session_id: str
    chunks: list[SourceChunk]


class FeedbackIn(BaseModel):
    """Body of POST /api/feedback."""

    session_id: str
    rating: Literal["up", "down"]
    comment: str = ""

    @field_validator("comment")
    @classmethod
    def _within_comment_limit(cls, comment: str) -> str:
        """Reject comments longer than the configured maximum."""
        limit = get_settings().max_comment_chars
        if len(comment) > limit:
            raise ValueError(f"comment longer than {limit} characters")
        return comment


class FeedbackOut(BaseModel):
    """Response of POST /api/feedback: False when this session already had feedback (nothing appended)."""

    recorded: bool


class ErrorBody(BaseModel):
    """Payload of every non-2xx response, wrapped as {"error": ErrorBody}."""

    code: str
    message: str
