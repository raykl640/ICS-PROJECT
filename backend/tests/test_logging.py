import io
import json
import logging

import pytest

from backend.app.config import Settings
from backend.app.logging_setup import REDACTED, configure_logging


def _emit(log_content: bool, **extra: object) -> dict[str, object]:
    stream = io.StringIO()
    configure_logging(Settings(log_content=log_content), stream=stream)
    logging.getLogger("haki.test").info("query_received", extra=extra)
    record: dict[str, object] = json.loads(stream.getvalue().strip().splitlines()[-1])
    return record


@pytest.fixture(autouse=True)
def _restore_root_logger() -> object:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_content_fields_redacted_by_default() -> None:
    record = _emit(False, question="my secret question", answer_en="draft", chunk_text="body", session_id="s1")
    assert "my secret question" not in json.dumps(record)
    assert record["question"] == REDACTED
    assert record["answer_en"] == REDACTED
    assert record["chunk_text"] == REDACTED
    assert record["session_id"] == "s1"
    assert record["msg"] == "query_received"
    assert record["level"] == "INFO"


def test_content_fields_kept_when_log_content_true() -> None:
    record = _emit(True, question="my secret question")
    assert record["question"] == "my secret question"


def test_ids_timings_and_counts_pass_through() -> None:
    record = _emit(False, session_id="s1", elapsed_ms=12.5, n_chunks=5)
    assert (record["elapsed_ms"], record["n_chunks"]) == (12.5, 5)


def test_exception_logs_type_only_not_traceback() -> None:
    stream = io.StringIO()
    configure_logging(Settings(), stream=stream)
    try:
        raise ValueError("contains user question text")
    except ValueError:
        logging.getLogger("haki.test").exception("stage_failed")
    record = json.loads(stream.getvalue().strip())
    assert record["exc_type"] == "ValueError"
    assert "user question" not in stream.getvalue()
