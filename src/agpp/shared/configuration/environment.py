import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from dotenv import dotenv_values

from agpp.shared.exceptions import ConfigurationError

ENVIRONMENT_VARIABLE = "AGPP_ENV"


class Environment(StrEnum):
    """Deployment environments, each with its own YAML overlay."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


def read_environment(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Combine an optional ``.env`` file with the process environment.
    The process environment wins over the file. ``os.environ`` is never modified.
    """
    values: dict[str, str] = {}
    if env_file is not None and env_file.is_file():
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    values.update(os.environ if environ is None else environ)
    return values


def resolve_environment(env: Mapping[str, str]) -> Environment:
    """Return the environment named by ``AGPP_ENV``; there is no default."""

    raw = env.get(ENVIRONMENT_VARIABLE, "").strip()
    allowed = ", ".join(item.value for item in Environment)
    if not raw:
        raise ConfigurationError(f"{ENVIRONMENT_VARIABLE} is not set; expected one of: {allowed}")
    try:
        return Environment(raw.lower())
    except ValueError:
        raise ConfigurationError(
            f"Unknown {ENVIRONMENT_VARIABLE} value {raw!r}; expected one of: {allowed}"
        ) from None
