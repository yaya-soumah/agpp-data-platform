"""Install log handlers from the logging configuration."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from agpp.shared.configuration.models import LoggingConfig
from agpp.shared.logging.formatters import ConsoleFormatter, JsonFormatter

CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_installed: list[logging.Handler] = []


def configure_logging(config: LoggingConfig) -> None:
    """Configure the root logger. Safe to call more than once."""
    reset_logging()

    formatter = _build_formatter(config)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if config.file is not None:
        path = Path(config.file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                path,
                maxBytes=config.file_max_bytes,
                backupCount=config.file_backup_count,
                encoding="utf-8",
            )
        )

    root = logging.getLogger()
    root.setLevel(config.level)
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)
        _installed.append(handler)


def reset_logging() -> None:
    """Remove and close the handlers installed by ``configure_logging``."""
    root = logging.getLogger()
    while _installed:
        handler = _installed.pop()
        root.removeHandler(handler)
        handler.close()


def _build_formatter(config: LoggingConfig) -> logging.Formatter:
    if config.format == "json":
        return JsonFormatter()
    return ConsoleFormatter(CONSOLE_FORMAT, DATE_FORMAT)
