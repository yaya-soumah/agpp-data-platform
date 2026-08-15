from pathlib import Path
from typing import Any

import yaml

from src.shared.exceptions import ConfigurationError

def load_yaml_file(path: Path) -> dict[str,Any]:
    """Load a YAML configuration file into a mapping."""

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError as exc:
        raise ConfigurationError(
            f"Configuration file not found: {path}",
            error_code="CONFIGURATION_FILE_NOT_FOUND"
        ) from exc
    except OSError as exc:
        raise ConfigurationError(
            f"Unable to read configuration file: {path}",
            error_code="READING_CONFIGURATION_FILE_FAILED"
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Invalid YAML configuration: {path}",
            error_code="INVALID_YAML__CONFIGURATION_FILE"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Configuration root must be a mapping: {path}",
            error_code="INVALID_CONFIGURATION_ROOT_TYPE"
        )
    return data
