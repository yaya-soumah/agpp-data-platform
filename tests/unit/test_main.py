import argparse
import shutil
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


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


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
    def failing(_config: PlatformConfig, _args: argparse.Namespace) -> int:
        raise AgppError("boom")

    monkeypatch.setitem(cli.COMMANDS, "check-config", failing)

    exit_code = cli.main([*cli_args, "check-config"])

    assert exit_code == cli.EXIT_ERROR
    assert "Command check-config failed" in caplog.text


def test_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([])

    assert exit_info.value.code == 2


def test_migrate_applies_migrations_and_closes_the_pool(
    cli_args: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakePool()
    monkeypatch.setattr(cli, "create_pool", lambda _config: fake)
    monkeypatch.setattr(cli, "apply_migrations", lambda _pool, _directory: [])

    exit_code = cli.main([*cli_args, "migrate"])

    assert exit_code == cli.EXIT_OK
    assert fake.closed


def test_generate_sample_data_writes_the_supplier_files(
    cli_args: list[str],
    tmp_path: Path,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = Path(cli_args[1])
    (config_dir / "pipelines").mkdir()
    shutil.copy(
        project_root / "config" / "pipelines" / "supplier_product.yaml",
        config_dir / "pipelines",
    )
    monkeypatch.setenv("AGPP_DATA_DIR", str(tmp_path / "data"))

    exit_code = cli.main([*cli_args, "generate-sample-data", "--rows", "20"])

    assert exit_code == cli.EXIT_OK
    written = sorted((tmp_path / "data" / "incoming" / "supplier_product").glob("*.csv"))
    assert [path.name for path in written] == ["sup-001.csv", "sup-002.csv", "sup-003.csv"]


def test_generate_sample_data_rejects_a_bad_ratio(
    cli_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([*cli_args, "generate-sample-data", "--bad-ratio", "2"])

    assert exit_info.value.code == 2
    assert "between 0 and 1" in capsys.readouterr().err
