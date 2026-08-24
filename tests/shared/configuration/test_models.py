import pytest
from pydantic import ValidationError
from src.shared.configuration.environment import Environment
from src.shared.configuration.models import AppConfig, LoggingConfig


@pytest.fixture
def valid_app_config_data() -> dict:
    return {
        "application": {
            "name": "AGPP Data Platform",
            "version": "0.1.0",
        },
        "environment_name": Environment.DEVELOPMENT,
        "environment": {
            "timezone": "UTC",
        },
        "pipeline": {
            "batch_size": 1000,
            "retry_attempts": 3,
        },
        "warehouse": {
            "schema": "analytics",
        },
        "database": {
            "port": 5432,
            "pool_size": 10,
            "connection_timeout": 30,
        },
        "paths": {
            "raw_data": "data/raw",
            "processed_data": "data/processed",
            "archive_data": "data/archive",
        },
        "features": {
            "enable_metrics": False,
            "enable_profiling": False,
        },
    }


@pytest.fixture
def valid_logging_config_data() -> dict:
    return {
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
                "path": "logs/agpp.log",
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


def test_valid_app_config_is_accepted(valid_app_config_data):
    config = AppConfig(**valid_app_config_data)

    assert config.application.name == "AGPP Data Platform"
    assert config.environment_name is Environment.DEVELOPMENT
    assert config.database.pool_size == 10


def test_valid_logging_config_is_accepted(valid_logging_config_data):
    config = LoggingConfig(**valid_logging_config_data)

    assert config.version == 1
    assert config.development.level == "DEBUG"
    assert config.production.level == "INFO"


def test_unknown_app_config_field_is_rejected(valid_app_config_data):
    valid_app_config_data["database"]["unknown_setting"] = True

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_invalid_batch_size_is_rejected(valid_app_config_data):
    valid_app_config_data["pipeline"]["batch_size"] = 0

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_invalid_numeric_type_is_rejected(valid_app_config_data):
    valid_app_config_data["pipeline"]["batch_size"] = "10"

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_invalid_boolean_type_is_rejected(valid_app_config_data):
    valid_app_config_data["features"]["enable_metrics"] = "false"

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_invalid_retry_attempts_is_rejected(valid_app_config_data):
    valid_app_config_data["pipeline"]["retry_attempts"] = -1

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_invalid_database_port_is_rejected(valid_app_config_data):
    valid_app_config_data["database"]["port"] = 70000

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_invalid_pool_size_is_rejected(valid_app_config_data):
    valid_app_config_data["database"]["pool_size"] = 0

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_empty_application_name_is_rejected(valid_app_config_data):
    valid_app_config_data["application"]["name"] = ""

    with pytest.raises(ValidationError):
        AppConfig(**valid_app_config_data)


def test_configuration_is_immutable(valid_app_config_data):
    config = AppConfig(**valid_app_config_data)

    with pytest.raises(ValidationError):
        config.database.pool_size = 20


def test_unknown_logging_field_is_rejected(valid_logging_config_data):
    valid_logging_config_data["unknown"] = True

    with pytest.raises(ValidationError):
        LoggingConfig(**valid_logging_config_data)


def test_rejects_invalid_logging_level(valid_logging_config_data):
    valid_logging_config_data["production"]["level"] = "BANANA"

    with pytest.raises(ValidationError):
        LoggingConfig(**valid_logging_config_data)
