import logging
from pathlib import Path

import pytest

from agpp.shared.configuration.environment import Environment
from agpp.shared.configuration.service import load_config
from agpp.shared.exceptions import (
    InvalidConfigurationError,
    MissingEnvironmentVariableError,
)

ENV = {
    "AGPP_ENV": "development",
    "POSTGRES_DB": "agpp",
    "POSTGRES_USER": "agpp",
    "POSTGRES_PASSWORD": "s3cret",
}


@pytest.mark.parametrize("environment", list(Environment))
def test_repository_config_loads_for_every_environment(
    project_root: Path, environment: Environment
) -> None:
    config = load_config(project_root / "config", environ={**ENV, "AGPP_ENV": environment.value})

    assert config.environment is environment
    assert config.database.name == "agpp"


def test_defaults_apply_when_optional_variables_are_unset(project_root: Path) -> None:
    config = load_config(project_root / "config", environ=ENV)

    assert config.database.host == "localhost"
    assert config.database.port == 5432


def test_overlay_overrides_base(project_root: Path) -> None:
    development = load_config(project_root / "config", environ=ENV)
    production = load_config(project_root / "config", environ={**ENV, "AGPP_ENV": "production"})

    assert development.app.debug is True
    assert production.app.debug is False
    assert production.database.pool_max_size == 10


def test_missing_secret_raises(project_root: Path) -> None:
    env = {key: value for key, value in ENV.items() if key != "POSTGRES_PASSWORD"}

    with pytest.raises(MissingEnvironmentVariableError):
        load_config(project_root / "config", environ=env)


def test_secret_is_hidden_in_repr(project_root: Path) -> None:
    config = load_config(project_root / "config", environ=ENV)

    assert "s3cret" not in repr(config)
    assert config.database.password.get_secret_value() == "s3cret"


def test_validation_error_does_not_leak_secrets(tmp_path: Path) -> None:
    (tmp_path / "base.yaml").write_text(
        "app:\n  name: x\n"
        "database:\n  host: h\n  port: 5432\n  name: d\n  user: u\n"
        "  password: ${POSTGRES_PASSWORD}\n  pool_min_size: 5\n  pool_max_size: 1\n",
        encoding="utf-8",
    )
    (tmp_path / "development.yaml").write_text("app:\n  debug: true\n", encoding="utf-8")

    with pytest.raises(InvalidConfigurationError) as info:
        load_config(tmp_path, environ={"AGPP_ENV": "development", "POSTGRES_PASSWORD": "s3cret"})

    assert "s3cret" not in str(info.value)
    assert "pool_min_size" in str(info.value)


def test_logs_the_environment_but_no_values(
    project_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        load_config(project_root / "config", environ=ENV)

    assert "development" in caplog.text
    assert "s3cret" not in caplog.text


def test_logging_settings_follow_the_overlays(project_root: Path) -> None:
    development = load_config(project_root / "config", environ=ENV)
    production = load_config(project_root / "config", environ={**ENV, "AGPP_ENV": "production"})

    assert development.logging.level == "DEBUG"
    assert development.logging.file == "logs/agpp.log"
    assert production.logging.format == "json"
    assert production.logging.file is None


def test_invalid_log_level_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "base.yaml").write_text(
        "app:\n  name: x\n"
        "database:\n  host: h\n  port: 5432\n  name: d\n  user: u\n"
        "  password: ${POSTGRES_PASSWORD}\n  pool_min_size: 1\n  pool_max_size: 2\n"
        "logging:\n  level: LOUD\n",
        encoding="utf-8",
    )
    (tmp_path / "development.yaml").write_text("app:\n  debug: true\n", encoding="utf-8")

    with pytest.raises(InvalidConfigurationError, match=r"logging\.level"):
        load_config(tmp_path, environ={"AGPP_ENV": "development", "POSTGRES_PASSWORD": "s3cret"})


def test_connect_timeout_comes_from_base_config(project_root: Path) -> None:
    config = load_config(project_root / "config", environ=ENV)

    assert config.database.connect_timeout_seconds == 10
