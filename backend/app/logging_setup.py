"""JSON logging with content redaction: question/answer/text fields are masked unless log_content=true."""

import json
import logging
import re
import sys
from typing import TextIO

from backend.app.config import Settings

REDACTED = "[redacted]"
_CONTENT_KEY = re.compile(r"question|answer|text|user_?name|display|password|recovery|profile|token", re.IGNORECASE)
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


def _extras(record: logging.LogRecord) -> dict[str, object]:
    """Fields passed via `extra=`, excluding the standard LogRecord attributes."""
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS}


class RedactContentFilter(logging.Filter):
    """Replaces any extra field whose name mentions content (question, answer, text) or account secrets/identity."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask content fields in place; never drops the record."""
        for key in _extras(record):
            if _CONTENT_KEY.search(key):
                setattr(record, key, REDACTED)
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, msg, then any extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialise the record; non-JSON values fall back to str()."""
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **_extras(record),
        }
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings, stream: TextIO | None = None, level: int = logging.INFO) -> None:
    """Route the root logger to a single JSON handler, redacting content unless settings.log_content."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    if not settings.log_content:
        handler.addFilter(RedactContentFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
