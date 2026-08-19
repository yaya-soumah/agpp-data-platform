import logging
from pathlib import Path

from src.shared.configuration.environment import Environment
from src.shared.configuration.models import LoggingConfig
from src.shared.exceptions import InfrastructureError


AGPP_LOGGER_NAME = "agpp"


def _resolve_log_level(
    config: LoggingConfig,
    environment: Environment,
) -> int:
    """Resolve the Python logging level for the active environment."""

    environment_config = getattr(config, environment.value)

    return getattr(
        logging,
        environment_config.level,
    )


def _create_formatter(config: LoggingConfig) -> logging.Formatter:
    """Create a logging formatter from validated configuration."""

    return logging.Formatter(
        config.format.standard
    )


def _create_file_handler(
    config: LoggingConfig,
) -> logging.FileHandler:
    """Create and configure the AGPP file handler."""

    path = Path(config.handlers.file.path)

    try:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        return logging.FileHandler(
            path,
            encoding="utf-8",
        )

    except OSError as exc:
        raise InfrastructureError(
            f"Unable to initialize log file: {path}",
            error_code="LOGGING_FILE_HANDLER_INITIALIZATION_FAILED",
            context={"path": str(path)},
        ) from exc


def configure_logging(
    config: LoggingConfig,
    environment: Environment,
) -> None:
    """Configure the AGPP runtime logging system."""

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    level = _resolve_log_level(
        config,
        environment,
    )

    formatter = _create_formatter(config)

    new_handlers: list[logging.Handler] = []

    try:
        if config.handlers.console.enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            new_handlers.append(console_handler)

        if config.handlers.file.enabled:
            file_handler = _create_file_handler(config)
            file_handler.setFormatter(formatter)
            new_handlers.append(file_handler)

    except Exception:
        for handler in new_handlers:
            handler.close()

        raise

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(level)
    logger.propagate = False

    for handler in new_handlers:
        logger.addHandler(handler)