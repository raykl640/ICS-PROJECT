"""Shared data types passed between pipeline stages and the API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["auto", "en", "sw"]


class LegalChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    act: str
    part: str
    section_num: str
    section_title: str
    text: str
    page: int
    act_year: int


class ScoredChunk(BaseModel):
    chunk: LegalChunk
    score: float


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, pattern=r"\S")
    language: Language = "auto"


class QueryResponse(BaseModel):
    session_id: str
    fallback: bool


class ParsedResponse(BaseModel):
    rights: str = ""
    steps: str = ""
    letter: str = ""
