import json
import logging
import sys
from pathlib import Path

from agpp.shared.logging.formatters import ConsoleFormatter, JsonFormatter


def _record(**attributes: object) -> logging.LogRecord:
    base: dict[str, object] = {
        "name": "agpp.test",
        "levelno": logging.INFO,
        "levelname": "INFO",
        "msg": "hello %s",
        "args": ("world",),
    }
    return logging.makeLogRecord({**base, **attributes})


def test_json_formatter_outputs_core_fields_and_extras() -> None:
    payload = json.loads(JsonFormatter().format(_record(rows=3)))

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "agpp.test"
    assert payload["rows"] == 3
    assert payload["timestamp"].endswith("+00:00")


def test_json_formatter_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record(exc_info=sys.exc_info())

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_json_core_fields_win_over_extras() -> None:
    payload = json.loads(JsonFormatter().format(_record(**{"level": "EVIL"})))

    assert payload["level"] == "INFO"


def test_json_formatter_stringifies_unserializable_values() -> None:
    payload = json.loads(JsonFormatter().format(_record(path=Path("a"))))

    assert payload["path"] == "a"


def test_console_formatter_appends_sorted_extras() -> None:
    line = ConsoleFormatter("%(message)s").format(_record(run_id="r1", rows=3))

    assert line == "hello world rows=3 run_id=r1"
