from pathlib import Path

import pytest

from agpp.shared.configuration.environment import (
    Environment,
    read_environment,
    resolve_environment,
)
from agpp.shared.exceptions import ConfigurationError


def test_resolves_known_environment() -> None:
    assert resolve_environment({"AGPP_ENV": "testing"}) is Environment.TESTING


def test_environment_name_is_case_insensititive_and_trimmed() -> None:
    assert resolve_environment({"AGPP_ENV": "Production"}) is Environment.PRODUCTION


@pytest.mark.parametrize("env", [{}, {"AGPP_ENV": ""}, {"AGPP_ENV": " "}])
def test_missing_environment_raises(env: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError, match="AGPP_ENV is not set"):
        resolve_environment(env)


def test_unknown_environment_raises() -> None:
    with pytest.raises(ConfigurationError, match="staging"):
        resolve_environment({"AGPP_ENV": "staging"})


def test_process_environment_overrides_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A=from_file\nB=from_file\n", encoding="utf-8")

    result = read_environment(env_file, {"A": "from_env"})

    assert result == {"A": "from_env", "B": "from_file"}


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    assert read_environment(tmp_path / "absent.env", {"A": "1"}) == {"A": "1"}
