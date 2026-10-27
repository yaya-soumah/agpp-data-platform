import json
import logging
from pathlib import Path

import pytest

from agpp.shared.configuration.models import LoggingConfig
from agpp.shared.logging import configure_logging, reset_logging


def test_sets_root_level_and_adds_a_console_handler(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LoggingConfig(level="INFO", format="console"))

    logging.getLogger("agpp.test").info("hello", extra={"rows": 3})

    assert logging.getLogger().level == logging.INFO
    err = capsys.readouterr().err
    assert "hello" in err
    assert "rows=3" in err


def test_json_file_handler_writes_structured_lines(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "agpp.log"
    configure_logging(LoggingConfig(level="INFO", format="json", file=str(log_file)))

    logging.getLogger("agpp.test").info("hello", extra={"rows": 3})
    for handler in logging.getLogger().handlers:
        handler.flush()

    payload = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["message"] == "hello"
    assert payload["rows"] == 3


def test_calling_twice_does_not_duplicate_handlers() -> None:
    config = LoggingConfig(level="INFO")
    configure_logging(config)
    after_first = len(logging.getLogger().handlers)

    configure_logging(config)

    assert len(logging.getLogger().handlers) == after_first


def test_reset_removes_installed_handlers() -> None:
    before = len(logging.getLogger().handlers)
    configure_logging(LoggingConfig(level="INFO"))

    reset_logging()

    assert len(logging.getLogger().handlers) == before


def test_level_filters_records(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggingConfig(level="WARNING"))

    logging.getLogger("agpp.test").info("quiet")
    logging.getLogger("agpp.test").warning("loud")

    err = capsys.readouterr().err
    assert "quiet" not in err
    assert "loud" in err
