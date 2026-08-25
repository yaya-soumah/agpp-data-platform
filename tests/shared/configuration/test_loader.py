from pathlib import Path

import pytest
from src.shared.configuration.loader import load_yaml_file
from src.shared.exceptions import ConfigurationError


def test_load_yaml_file_returns_mapping(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "database:\n   port: 5432\n",
        encoding="utf-8",
    )

    result = load_yaml_file(config_file)

    assert result == {"database": {"port": 5432}}


def test_missing_file_raises_configuration_error(tmp_path: Path):
    config_file = tmp_path / "missing.yaml"
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_yaml_file(config_file)


def test_invalid_yaml_raises_configuration_error(tmp_path: Path):
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("database:\n   port: [5432\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid YAML configuration"):
        load_yaml_file(config_file)


def test_non_mapping_root_raises_configuration_error(tmp_path: Path):
    config_file = tmp_path / "invalid-root.yaml"
    config_file.write_text(
        "- database\n- pipeline\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigurationError, match="Configuration root must be a mapping"
    ):
        load_yaml_file(config_file)


def test_empty_yaml_raises_configuration_error(tmp_path: Path):
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("", encoding="utf-8")

    with pytest.raises(
        ConfigurationError, match="Configuration root must be a mapping"
    ):
        load_yaml_file(config_file)
