"""Errors raised when loading or validating configuration."""

from agpp.shared.exceptions.base import AgppError


class ConfigurationError(AgppError):
    """Configuration is missing, unreadable or invalid."""


class ConfigurationFileError(ConfigurationError):
    """A configuration file is missing or is not valid YAML."""


class InvalidConfigurationError(ConfigurationError):
    """Configuration was read but failed validation."""


class MissingEnvironmentVariableError(ConfigurationError):
    """A required environment variable is not set."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Environment variable {name!r} is required but not set")
        self.name = name
