from agpp.shared.exceptions import (
    AgppError,
    ConfigurationError,
    ConfigurationFileError,
    InvalidConfigurationError,
    MissingEnvironmentVariableError,
)


def test_configuration_errors_share_a_base() -> None:
    for error_class in (
        ConfigurationFileError,
        InvalidConfigurationError,
        MissingEnvironmentVariableError,
    ):
        assert issubclass(error_class, ConfigurationError)
    assert issubclass(ConfigurationError, AgppError)


def test_missing_variable_message_names_the_variable() -> None:
    error = MissingEnvironmentVariableError("FOO")

    assert "FOO" in str(error)
    assert error.name == "FOO"
