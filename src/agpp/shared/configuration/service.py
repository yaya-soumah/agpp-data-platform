"""Build the validated platform configuration."""

import logging
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from agpp.shared.configuration.environment import read_environment, resolve_environment
from agpp.shared.configuration.environment_resolver import resolve_placeholders
from agpp.shared.configuration.loader import load_yaml_file
from agpp.shared.configuration.merger import deep_merge
from agpp.shared.configuration.models import PlatformConfig
from agpp.shared.exceptions import InvalidConfigurationError

logger = logging.getLogger(__name__)


def load_config(
    config_dir: Path,
    *,
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> PlatformConfig:
    """Load ``base.yaml`` plus the environment overlay and validate the result."""
    env = read_environment(env_file, environ)
    environment = resolve_environment(env)

    base = load_yaml_file(config_dir / "base.yaml")
    overlay = load_yaml_file(config_dir / f"{environment.value}.yaml")
    resolved = resolve_placeholders(deep_merge(base, overlay), env)
    resolved["environment"] = environment.value

    try:
        config = PlatformConfig.model_validate(resolved)
    except ValidationError as error:
        raise InvalidConfigurationError(_describe(error)) from error

    logger.info("Loaded configuration for environment %s", environment.value)
    return config


def _describe(error: ValidationError) -> str:
    """Summarize validation problems by field and reason, never by input value."""
    problems = [
        f"{'.'.join(str(part) for part in item['loc']) or 'config'}: {item['msg']}"
        for item in error.errors()
    ]
    return "Invalid configuration: " + "; ".join(problems)
