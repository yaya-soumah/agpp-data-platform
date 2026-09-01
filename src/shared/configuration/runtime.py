import os

from pydantic import SecretStr
from src.shared.exceptions import ConfigurationError


class RuntimeEnvironment:
    """Provides access to runtime environment variables."""

    def get_required(self, name: str) -> str:
        """Return a required runtime environment variable."""

        if not name.strip():
            raise ConfigurationError(
                "Environment variable name must not be blank.",
                error_code="CONFIG_RUNTIME_VARIABLE_NAME_INVALID",
            )
        value = os.getenv(name)

        if value is None or not value.strip():
            raise ConfigurationError(
                f"Required environment variable '{name}' is not set.",
                error_code="CONFIG_RUNTIME_VARIABLE_NOT_SET",
            )

        return value

    def get_required_secret(self, name: str) -> SecretStr:
        """Return a required runtime environment variable as a secret."""

        value = self.get_required(name)
        return SecretStr(value)
