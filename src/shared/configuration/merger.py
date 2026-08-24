from collections.abc import Mapping
from copy import deepcopy
from typing import Any


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Deep merge override values into a new configuration mapping."""

    result = deepcopy(dict(base))
    override_copy = deepcopy(dict(override))

    for key, override_value in override_copy.items():
        base_value = result.get(key)

        if isinstance(base_value, Mapping) and isinstance(override_value, Mapping):
            result[key] = deep_merge(base_value, override_value)
        else:
            result[key] = override_value
    return result
