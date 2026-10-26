from pathlib import Path

import pytest

from agpp.shared.configuration.loader import load_yaml_file
from agpp.shared.exceptions import ConfigurationFileError


def _write(directory: Path, text: str) -> Path:
    path = directory / "sample.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_mapping(tmp_path: Path) -> None:
    path = _write(tmp_path, "app:\n  name: x\n")

    assert load_yaml_file(path) == {"app": {"name": "x"}}


def test_empty_file_is_an_empty_mapping(tmp_path: Path) -> None:
    assert load_yaml_file(_write(tmp_path, "")) == {}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationFileError, match="not found"):
        load_yaml_file(tmp_path / "absent.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationFileError, match="Invalid YAML"):
        load_yaml_file(_write(tmp_path, "a: [unclosed"))


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationFileError, match="must be a mapping"):
        load_yaml_file(_write(tmp_path, "- a\n- b\n"))
