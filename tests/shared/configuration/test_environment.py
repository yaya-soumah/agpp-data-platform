import pytest
from src.shared.configuration.environment import Environment, resolve_environment
from src.shared.exceptions import ConfigurationError


def test_development_environment_is_resolved() -> None:
    assert resolve_environment("development") is Environment.DEVELOPMENT


def test_testing_environment_is_resolved() -> None:
    assert resolve_environment("testing") is Environment.TESTING


def test_production_environment_is_resolved() -> None:
    assert resolve_environment("production") is Environment.PRODUCTION


def test_unsupported_environment_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="Unsupported environment"):
        resolve_environment("stagging")


def test_environment_resolution_is_case_sentitive() -> None:
    with pytest.raises(ConfigurationError):
        resolve_environment("Production")


def test_non_string_environment_raises_configuration_error() -> None:
    with pytest.raises(
        ConfigurationError, match="Environment value type must be a string"
    ):
        resolve_environment(123)
