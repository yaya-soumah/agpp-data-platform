import pytest

from agpp.shared.configuration.environment_resolver import resolve_placeholders
from agpp.shared.exceptions import MissingEnvironmentVariableError

ENV = {"HOST": "db.local", "EMPTY": ""}


def test_replaces_placeholder() -> None:
    assert resolve_placeholders("${HOST}", ENV) == "db.local"


def test_uses_default_when_unset() -> None:
    assert resolve_placeholders("${PORT:-5432}", ENV) == "5432"


def test_uses_default_when_empty() -> None:
    assert resolve_placeholders("${EMPTY:-fallback}", ENV) == "fallback"


def test_value_wins_over_default() -> None:
    assert resolve_placeholders("${HOST:-other}", ENV) == "db.local"


def test_embedded_placeholders() -> None:
    assert resolve_placeholders("pg://${HOST}:${PORT:-1}", ENV) == "pg://db.local:1"


def test_nested_structures_are_resolved() -> None:
    data = {"a": ["${HOST}", {"b": "${HOST}"}], "n": 3, "flag": True}

    assert resolve_placeholders(data, ENV) == {
        "a": ["db.local", {"b": "db.local"}],
        "n": 3,
        "flag": True,
    }


def test_missing_variable_raises() -> None:
    with pytest.raises(MissingEnvironmentVariableError) as info:
        resolve_placeholders("${NOPE}", ENV)

    assert info.value.name == "NOPE"
