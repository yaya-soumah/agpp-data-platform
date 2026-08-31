import logging

import pytest
from src.shared.configuration.environment import Environment
from src.shared.configuration.models import (
    LoggingConfig,
)
from src.shared.exceptions import InfrastructureError
from src.shared.logging.setup import (
    AGPP_LOGGER_NAME,
    configure_logging,
)


@pytest.fixture
def logging_config(tmp_path) -> LoggingConfig:
    return LoggingConfig.model_validate(
        {
            "version": 1,
            "format": {
                "standard": ("%(asctime)s | %(levelname)s | %(name)s | %(message)s"),
            },
            "handlers": {
                "console": {
                    "enabled": True,
                },
                "file": {
                    "enabled": True,
                    "path": str(tmp_path / "logs" / "agpp.log"),
                },
            },
            "development": {
                "level": "DEBUG",
            },
            "testing": {
                "level": "WARNING",
            },
            "production": {
                "level": "INFO",
            },
        }
    )


@pytest.fixture(autouse=True)
def clean_agpp_logger() -> None:
    logger = logging.getLogger(AGPP_LOGGER_NAME)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(logging.NOTSET)
    logger.propagate = True

    yield

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def test_development_uses_debug_level(logging_config) -> None:
    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    assert logger.level == logging.DEBUG


def test_testing_uses_warning_level(logging_config) -> None:
    configure_logging(
        logging_config,
        Environment.TESTING,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    assert logger.level == logging.WARNING


def test_production_uses_info_level(logging_config) -> None:
    configure_logging(
        logging_config,
        Environment.PRODUCTION,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    assert logger.level == logging.INFO


def test_enabled_console_handler_is_created(logging_config) -> None:
    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    console_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    ]

    assert len(console_handlers) == 1


def test_enabled_file_handler_is_created(
    logging_config,
    tmp_path,
) -> None:
    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    file_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    ]

    assert len(file_handlers) == 1
    assert (tmp_path / "logs" / "agpp.log").exists()


def test_disabled_console_handler_is_not_created(
    logging_config,
) -> None:
    config = logging_config.model_copy(
        update={
            "handlers": logging_config.handlers.model_copy(
                update={
                    "console": logging_config.handlers.console.model_copy(
                        update={"enabled": False}
                    )
                }
            )
        }
    )

    configure_logging(
        config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    console_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    ]

    assert console_handlers == []


def test_disabled_file_handler_is_not_created(
    logging_config,
) -> None:
    config = logging_config.model_copy(
        update={
            "handlers": logging_config.handlers.model_copy(
                update={
                    "file": logging_config.handlers.file.model_copy(
                        update={"enabled": False}
                    )
                }
            )
        }
    )

    configure_logging(
        config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    file_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    ]

    assert file_handlers == []


def test_configured_formatter_is_applied(
    logging_config,
) -> None:
    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    assert len(logger.handlers) == 2

    for handler in logger.handlers:
        assert handler.formatter is not None
        assert handler.formatter._fmt == logging_config.format.standard


def test_agpp_logger_does_not_propagate(
    logging_config,
) -> None:
    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    assert logger.propagate is False


def test_configure_logging_is_idempotent(
    logging_config,
) -> None:
    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    configure_logging(
        logging_config,
        Environment.DEVELOPMENT,
    )

    logger = logging.getLogger(AGPP_LOGGER_NAME)

    assert len(logger.handlers) == 2

    file_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    ]

    console_handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
    ]

    assert len(file_handlers) == 1
    assert len(console_handlers) == 1


def test_file_handler_failure_becomes_infrastructure_error(
    logging_config,
    monkeypatch,
) -> None:
    def fail_mkdir(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(
        "pathlib.Path.mkdir",
        fail_mkdir,
    )

    with pytest.raises(InfrastructureError) as exc:
        configure_logging(
            logging_config,
            Environment.DEVELOPMENT,
        )

    assert exc.value.error_code == "LOGGING_FILE_HANDLER_INITIALIZATION_FAILED"

    assert isinstance(
        exc.value.__cause__,
        OSError,
    )
