from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from src.shared.configuration.environment import Environment
from src.shared.configuration.loader import load_yaml_file
from src.shared.configuration.merger import deep_merge
from src.shared.configuration.models import AppConfig, LoggingConfig
from src.shared.exceptions import ConfigurationError
from src.shared.configuration.environment_resolver import EnvironmentResolver

@dataclass(frozen=True)
class Configuration:
    """Validated AGPP application and logging configuration."""

    app: AppConfig
    logging: LoggingConfig

class ConfigurationService:
    """Build validated AGPP configuration for an environment."""

    def __init__(
            self,
            config_directory: Path,
            environment_resolver: EnvironmentResolver | None = None
            ):
        
        self._config_directory = config_directory
        self._environment_resolver = (
            environment_resolver
            if environment_resolver is not None
            else EnvironmentResolver()
        )

    def load(self, environment: Environment | None = None) -> Configuration:

        if environment is None:
            environment = self._environment_resolver.resolve()

        base_config = load_yaml_file(self._config_directory / "base.yaml")
        environment_config = load_yaml_file(self._config_directory / f"{environment.value}.yaml")

        merged_config = deep_merge(base_config, environment_config)

        app_config = self._build_app_config(
            merged_config, environment
        )

        logging_config = self._build_logging_config()

        return Configuration(
            app=app_config,
            logging=logging_config
        )

    def _build_app_config(self, config: dict[str,Any], environment: Environment) ->AppConfig:

        try:
            config_with_environment = {**config, "environment_name": environment}
            return AppConfig.model_validate(config_with_environment)
        except ValidationError as exc:
            raise ConfigurationError(
                "Invalid application configuration.",
                error_code="CONFIG_VALIDATION_ERROR",
                context={"environment": environment.value}
            ) from exc

    def _build_logging_config(self) -> LoggingConfig:

        logging_path = self._config_directory / "logging.yaml"

        raw_logging = load_yaml_file(logging_path)

        try:
            logging_section = raw_logging["logging"]        
        except KeyError as exc:
            raise ConfigurationError(
                "Logging configuration must contain a 'logging' section",
                error_code="CONFIG_MISSING_SECTION",
                context={ "file": str(logging_path)}
            ) from exc

        try:
            return LoggingConfig.model_validate(logging_section)
        except ValidationError as exc:
            raise ConfigurationError(
                "Logging configuration is invalid.",
                error_code="CONFIG_VALIDATION_ERROR",
                context={
                    "file": str(logging_path)
                }
            ) from exc
        
        