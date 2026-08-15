from enum import Enum
from src.shared.exceptions import ConfigurationError

class Environment(Enum):
    """Enum representing different application environments."""
    
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

def resolve_environment(value: str) -> Environment:
    """Resolve a configuration value into an AGPP Environment."""

    if not isinstance(value, str):
        raise ConfigurationError(
            "Environment value type must be a string",
            error_code="UNSUPPORTED_ENVIRONMENT_VALUE_TYPE"
        )
    try:
        return Environment(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Unsupported environment: {value!r}",
            error_code="UNSUPPORTED_ENVIRONMENT_VALUE"
        ) from exc
    