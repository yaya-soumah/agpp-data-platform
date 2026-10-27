from pathlib import Path

import pytest

import agpp.main as cli
from agpp.shared.configuration.models import PlatformConfig
from agpp.shared.exceptions import AgppError

BASE_CONFIG = """\
app:
  name: test
database:
  host: localhost
  port: 5432
  name: agpp
  user: agpp
  password: ${POSTGRES_PASSWORD}
  pool_min_size: 1
  pool_max_size: 2
logging:
  level: INFO
  format: console
  file: null
"""


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGPP_ENV", "development")
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")


@pytest.fixture
def cli_args(tmp_path: Path) -> list[str]:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text(BASE_CONFIG, encoding="utf-8")
    (config_dir / "development.yaml").write_text("app:\n  debug: true\n", encoding="utf-8")
    return ["--config-dir", str(config_dir), "--env-file", str(tmp_path / "absent.env")]


def test_check_config_succeeds_and_logs(
    cli_args: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    exit_code = cli.main([*cli_args, "check-config"])

    assert exit_code == cli.EXIT_OK
    assert "Configuration is valid" in caplog.text


def test_missing_environment_is_a_configuration_error(
    cli_args: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AGPP_ENV")

    exit_code = cli.main([*cli_args, "check-config"])

    assert exit_code == cli.EXIT_CONFIGURATION_ERROR
    assert "AGPP_ENV is not set" in capsys.readouterr().err


def test_missing_config_directory_is_a_configuration_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["--config-dir", str(tmp_path / "absent"), "--env-file", str(tmp_path / "x.env")]

    exit_code = cli.main([*args, "check-config"])

    assert exit_code == cli.EXIT_CONFIGURATION_ERROR
    assert "not found" in capsys.readouterr().err


def test_platform_error_in_a_command_returns_error_code(
    cli_args: list[str], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(_config: PlatformConfig) -> int:
        raise AgppError("boom")

    monkeypatch.setitem(cli.COMMANDS, "check-config", failing)

    exit_code = cli.main([*cli_args, "check-config"])

    assert exit_code == cli.EXIT_ERROR
    assert "Command check-config failed" in caplog.text


def test_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([])

    assert exit_info.value.code == 2
