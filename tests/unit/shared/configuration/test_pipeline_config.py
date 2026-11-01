from pathlib import Path

import pytest
from pydantic import BaseModel

from agpp.shared.configuration.service import load_pipeline_config
from agpp.shared.exceptions import (
    ConfigurationFileError,
    InvalidConfigurationError,
    MissingEnvironmentVariableError,
)


class DemoConfig(BaseModel):
    name: str
    port: int


def _write(config_dir: Path, text: str) -> None:
    pipelines = config_dir / "pipelines"
    pipelines.mkdir(parents=True, exist_ok=True)
    (pipelines / "demo.yaml").write_text(text, encoding="utf-8")


def test_loads_and_validates_a_pipeline_file(tmp_path: Path) -> None:
    _write(tmp_path, "name: demo\nport: 8080\n")

    config = load_pipeline_config(tmp_path, "demo", DemoConfig, environ={})

    assert config == DemoConfig(name="demo", port=8080)


def test_placeholders_are_resolved(tmp_path: Path) -> None:
    _write(tmp_path, "name: ${DEMO_NAME}\nport: ${DEMO_PORT:-9000}\n")

    config = load_pipeline_config(tmp_path, "demo", DemoConfig, environ={"DEMO_NAME": "x"})

    assert config == DemoConfig(name="x", port=9000)


def test_missing_variable_raises(tmp_path: Path) -> None:
    _write(tmp_path, "name: ${DEMO_NAME}\nport: 1\n")

    with pytest.raises(MissingEnvironmentVariableError):
        load_pipeline_config(tmp_path, "demo", DemoConfig, environ={})


def test_invalid_values_raise_without_leaking_the_input(tmp_path: Path) -> None:
    _write(tmp_path, "name: demo\nport: s3cret-value\n")

    with pytest.raises(InvalidConfigurationError) as info:
        load_pipeline_config(tmp_path, "demo", DemoConfig, environ={})

    assert "port" in str(info.value)
    assert "s3cret-value" not in str(info.value)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationFileError, match="not found"):
        load_pipeline_config(tmp_path, "demo", DemoConfig, environ={})
