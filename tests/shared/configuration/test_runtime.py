import pytest
from pydantic import SecretStr
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.exceptions import ConfigurationError


@pytest.fixture
def runtime_environment() -> RuntimeEnvironment:
    return RuntimeEnvironment()


def test_get_required_returns_environment_variable(
    runtime_environment: RuntimeEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_RUNTIME_VALUE", "runtime-value")

    assert runtime_environment.get_required("TEST_RUNTIME_VALUE") == "runtime-value"


def test_get_required_raises_when_variable_is_missing(
    runtime_environment: RuntimeEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_RUNTIME_VALUE", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        runtime_environment.get_required("TEST_RUNTIME_VALUE")

    assert exc_info.value.error_code == "CONFIG_RUNTIME_VARIABLE_NOT_SET"


def test_get_required_raises_when_variable_is_empty(
    runtime_environment: RuntimeEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_RUNTIME_VALUE", "")

    with pytest.raises(ConfigurationError) as exc_info:
        runtime_environment.get_required("TEST_RUNTIME_VALUE")

    assert exc_info.value.error_code == "CONFIG_RUNTIME_VARIABLE_NOT_SET"


def test_get_required_raises_when_variable_is_whitespace(
    runtime_environment: RuntimeEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_RUNTIME_VALUE", " ")

    with pytest.raises(ConfigurationError) as exc_info:
        runtime_environment.get_required("TEST_RUNTIME_VALUE")

    assert exc_info.value.error_code == "CONFIG_RUNTIME_VARIABLE_NOT_SET"


@pytest.mark.parametrize("name", ["", " "])
def test_get_required_rejects_blank_variable_name(
    runtime_environment: RuntimeEnvironment,
    name: str,
) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        runtime_environment.get_required(name)

    assert exc_info.value.error_code == "CONFIG_RUNTIME_VARIABLE_NAME_INVALID"


def test_get_required_secret_returns_secret_str(
    runtime_environment: RuntimeEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_RUNTIME_SECRET", "super-secret")

    result = runtime_environment.get_required_secret("TEST_RUNTIME_SECRET")

    assert isinstance(result, SecretStr)
    assert result.get_secret_value() == "super-secret"


def test_get_required_secret_does_not_expose_secret_in_repr(
    runtime_environment: RuntimeEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_RUNTIME_SECRET", "super-secret")

    result = runtime_environment.get_required_secret("TEST_RUNTIME_SECRET")

    assert "super-secret" not in repr(result)
