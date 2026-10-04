import pytest
from pydantic import ValidationError

from backend.app.models import (
    LegalChunk,
    ParsedResponse,
    QueryRequest,
    QueryResponse,
    ScoredChunk,
)


def _chunk() -> LegalChunk:
    return LegalChunk(
        chunk_id="employment-act:41",
        act="Employment Act",
        part="PART VI — TERMINATION AND DISMISSAL",
        section_num="41",
        section_title="Notification and hearing before termination on grounds of misconduct",
        text="(1) An employer shall ...",
        page=23,
        act_year=2007,
    )


def test_legal_chunk_roundtrips_json() -> None:
    chunk = _chunk()
    assert LegalChunk.model_validate_json(chunk.model_dump_json()) == chunk


def test_legal_chunk_is_immutable() -> None:
    with pytest.raises(ValidationError):
        _chunk().page = 1  # type: ignore[misc]


def test_scored_chunk() -> None:
    assert ScoredChunk(chunk=_chunk(), score=1.5).score == 1.5


def test_query_request_defaults_to_auto_and_rejects_blank() -> None:
    assert QueryRequest(question="Nimefukuzwa kazi").language == "auto"
    with pytest.raises(ValidationError):
        QueryRequest(question="   ")
    with pytest.raises(ValidationError):
        QueryRequest(question="hi", language="fr")  # type: ignore[arg-type]


def test_query_response_and_parsed_response() -> None:
    assert QueryResponse(session_id="abc", fallback=True).fallback
    assert ParsedResponse().letter == ""
