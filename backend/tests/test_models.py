import pytest
from pydantic import ValidationError

from backend.app.models import (
    CitationCheck,
    ErrorBody,
    FeedbackIn,
    LegalChunk,
    ParsedResponse,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
    SessionData,
)


def _chunk(**overrides: object) -> LegalChunk:
    fields: dict[str, object] = {
        "chunk_id": "sample-act-12",
        "act": "Sample Act",
        "act_slug": "sample-act",
        "act_year": 2000,
        "unit_type": "section",
        "part": "PART II — SAMPLE",
        "section_num": "12",
        "section_title": "Sample heading",
        "text": "Synthetic fixture text.",
        "page": 3,
        "source_sha256": "0" * 64,
    }
    return LegalChunk.model_validate(fields | overrides)


def test_legal_chunk_defaults_and_json_roundtrip() -> None:
    chunk = _chunk()
    assert chunk.chapter == ""
    assert chunk.repealed is False
    assert LegalChunk.model_validate_json(chunk.model_dump_json()) == chunk


def test_legal_chunk_is_immutable() -> None:
    with pytest.raises(ValidationError):
        _chunk().page = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    "bad",
    [{"unit_type": "clause"}, {"chunk_id": "Sample Act:12"}, {"page": 0}, {"source_sha256": "xyz"}],
)
def test_legal_chunk_rejects_invalid_fields(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _chunk(**bad)


def test_retrieved_chunk_ranks_are_optional() -> None:
    rc = RetrievedChunk(chunk=_chunk(), dense_rank=1, sparse_rank=None, rrf_score=1 / 61)
    assert rc.rerank_score is None
    assert rc.truncated is False


def test_query_request_defaults_to_auto_and_rejects_blank_or_unknown_language() -> None:
    assert QueryRequest(question="Nimefukuzwa kazi").language == "auto"
    with pytest.raises(ValidationError):
        QueryRequest(question="   ")
    with pytest.raises(ValidationError):
        QueryRequest(question="hi", language="fr")


def test_query_request_enforces_max_question_chars() -> None:
    QueryRequest(question="a" * 1000)
    with pytest.raises(ValidationError):
        QueryRequest(question="a" * 1001)


def test_session_data_starts_pending() -> None:
    session = SessionData(question="q", question_en="q", lang="en", chunks=[], fallback=True)
    assert (session.status, session.answer_en, session.parsed, session.parsed_user) == ("pending", "", None, None)
    assert (session.acts, session.untranslated, session.feedback_given) == ([], [], False)


def test_api_schemas() -> None:
    assert QueryResponse(session_id="abc", null_response=True, acts=[], language="sw").null_response
    assert ParsedResponse().letter == ""
    assert CitationCheck().unmatched == []
    assert ErrorBody(code="busy", message="Try again").code == "busy"
    assert FeedbackIn(session_id="abc", rating="up").comment == ""
    with pytest.raises(ValidationError):
        FeedbackIn(session_id="abc", rating="meh")
    with pytest.raises(ValidationError, match="500"):
        FeedbackIn(session_id="abc", rating="up", comment="x" * 501)
