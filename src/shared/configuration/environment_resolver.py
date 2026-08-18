from src.shared.configuration.environment import Environment, resolve_environment
from src.shared.exceptions import ConfigurationError
import os

ENVIRONMENT_VARIABLE = "AGPP_ENV"

class EnvironmentResolver:
    """Resolve the active AGPP environment from runtime environment """

    def resolve(self) -> Environment:
        value = os.getenv(ENVIRONMENT_VARIABLE)
        if value is None:
            raise ConfigurationError(
                f"Environment variable '{ENVIRONMENT_VARIABLE}' is not set",
                error_code="CONFIG_ENVIRONMENT_NOT_SET"
            )

        return resolve_environment(value)