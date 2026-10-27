"""Log formatters: readable console output and structured JSON."""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

_STANDARD_ATTRIBUTES = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Return the custom attributes a caller added through ``extra=...``."""
    return {key: value for key, value in record.__dict__.items() if key not in _STANDARD_ATTRIBUTES}


class ConsoleFormatter(logging.Formatter):
    """Human-readable lines in UTC; extra fields are appended as key=value."""

    converter = time.gmtime

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802
        line = super().formatMessage(record)
        extras = extra_fields(record)
        if extras:
            line += " " + " ".join(f"{key}={value}" for key, value in sorted(extras.items()))
        return line


class JsonFormatter(logging.Formatter):
    """One JSON object per record. Core fields cannot be overridden by extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            **extra_fields(record),
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
