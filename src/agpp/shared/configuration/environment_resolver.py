"""Resolve ${NAME} and ${NAME:-default} placeholders from environment values"""

import re
from collections.abc import Mapping
from typing import Any

from agpp.shared.exceptions import MissingEnvironmentVariableError

_PLACEHOLDER = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")


def resolve_placeholders(value: Any, env: Mapping[str, str]) -> Any:
    """Return ``value`` with every placeholder in its strings replaced.
    An unset or empty variable uses its default, or raises ``MissingEnvironmentVariableError``
    when there is none."""
    if isinstance(value, str):
        return _resolve_string(value, env)
    if isinstance(value, Mapping):
        return {key: resolve_placeholders(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(item, env) for item in value]
    return value


def _resolve_string(text: str, env: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        default = match.group("default")
        if env.get(name):
            return env[name]
        if default is not None:
            return default
        raise MissingEnvironmentVariableError(name)

    return _PLACEHOLDER.sub(replace, text)
