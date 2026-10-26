"""Read configuration files from disk."""

from pathlib import Path
from typing import Any

import yaml

from agpp.shared.exceptions import ConfigurationFileError


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Read a YAML file whose top level is a mapping; an empty file gives ``{}.``"""
    if not path.is_file():
        raise ConfigurationFileError(f"Configuration file not found: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            content = yaml.safe_load(handle)
    except yaml.YAMLError as error:
        raise ConfigurationFileError(f"Invalid YAML in {path}: {error}") from error
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ConfigurationFileError(f"Top level of {path} must be a mapping")
    return content
