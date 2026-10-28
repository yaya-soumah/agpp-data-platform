from agpp.shared.exceptions import AgppError, MissingEnvironmentVariableError
from agpp.shared.exceptions.configuration import ConfigurationError


def test_defaults() -> None:
    error = AgppError("boom")

    assert str(error) == "boom"
    assert error.message == "boom"
    assert error.context == {}
    assert error.retryable is False
    assert error.stage == "platform"


def test_context_is_stored() -> None:
    error = AgppError("boom", context={"file": "a.csv", "rows": 3})

    assert error.context == {"file": "a.csv", "rows": 3}


def test_context_is_copied_from_the_caller() -> None:
    source: dict[str, object] = {"file": "a.csv"}
    error = AgppError("boom", context=source)

    source["file"] = "changed"

    assert error.context == {"file": "a.csv"}


def test_missing_variable_error_names_the_variable() -> None:
    error = MissingEnvironmentVariableError("FOO")

    assert isinstance(error, ConfigurationError)
    assert "FOO" in str(error)
    assert error.name == "FOO"
    assert error.context == {"variable": "FOO"}
