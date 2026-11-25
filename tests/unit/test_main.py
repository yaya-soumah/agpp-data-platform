import argparse
from pathlib import Path

import pytest

import agpp.main as cli
from agpp.pipelines.customer_orders.service import RunSummary as OrdersRunSummary
from agpp.pipelines.inventory.service import RunSummary as InventoryRunSummary
from agpp.pipelines.supplier_product.loading import RunStatus
from agpp.pipelines.supplier_product.service import RunSummary
from agpp.shared.configuration.models import PlatformConfig
from agpp.shared.exceptions import AgppError
from agpp.shared.quality import CheckResult, CheckStatus, QualityCheck, QualitySummary

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


@pytest.fixture
def supplier_data_dir(
    cli_args: list[str], tmp_path: Path, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    pipelines = Path(cli_args[1]) / "pipelines"
    pipelines.mkdir()
    text = (project_root / "config" / "pipelines" / "supplier_product.yaml").read_text(
        encoding="utf-8"
    )
    text = text.replace("initial_delay_seconds: 1.0", "initial_delay_seconds: 0")
    (pipelines / "supplier_product.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setenv("AGPP_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data" / "incoming" / "supplier_product"


@pytest.fixture
def orders_data_dir(
    cli_args: list[str], tmp_path: Path, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    pipelines = Path(cli_args[1]) / "pipelines"
    pipelines.mkdir(exist_ok=True)
    text = (project_root / "config" / "pipelines" / "customer_orders.yaml").read_text(
        encoding="utf-8"
    )
    text = text.replace("initial_delay_seconds: 1.0", "initial_delay_seconds: 0")
    (pipelines / "customer_orders.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setenv("AGPP_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data" / "incoming" / "customer_orders"


@pytest.fixture
def inventory_config(
    cli_args: list[str], project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines = Path(cli_args[1]) / "pipelines"
    pipelines.mkdir(exist_ok=True)
    text = (project_root / "config" / "pipelines" / "inventory.yaml").read_text(encoding="utf-8")
    text = text.replace("initial_delay_seconds: 1.0", "initial_delay_seconds: 0")
    (pipelines / "inventory.yaml").write_text(text, encoding="utf-8")
    monkeypatch.delenv("INVENTORY_API_TOKEN", raising=False)
    monkeypatch.delenv("INVENTORY_API_URL", raising=False)


@pytest.fixture
def quality_config(
    cli_args: list[str], project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines = Path(cli_args[1]) / "pipelines"
    pipelines.mkdir(exist_ok=True)
    text = (project_root / "config" / "pipelines" / "data_quality.yaml").read_text(encoding="utf-8")
    (pipelines / "data_quality.yaml").write_text(text, encoding="utf-8")


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _summary(*statuses: CheckStatus) -> QualitySummary:
    check = QualityCheck.model_validate(
        {"name": "a_check", "description": "d", "sql": "SELECT 1", "warn": 0.1, "fail": 0.2}
    )
    return QualitySummary("run-1", tuple(CheckResult(check, s, 0.0) for s in statuses))


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
    cli_args: list[str], supplier_data_dir: Path
) -> None:
    exit_code = cli.main([*cli_args, "generate-sample-data", "--rows", "20"])

    assert exit_code == cli.EXIT_OK
    written = sorted(supplier_data_dir.glob("*.csv"))
    assert [path.name for path in written] == ["sup-001.csv", "sup-002.csv", "sup-003.csv"]


def test_generate_sample_data_rejects_a_bad_ratio(
    cli_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([*cli_args, "generate-sample-data", "--bad-ratio", "2"])

    assert exit_info.value.code == 2
    assert "between 0 and 1" in capsys.readouterr().err


def test_extract_supplier_products_reads_the_generated_files(
    cli_args: list[str], supplier_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cli.main([*cli_args, "generate-sample-data", "--rows", "20"])

    exit_code = cli.main([*cli_args, "extract-supplier-products"])

    assert exit_code == cli.EXIT_OK
    assert "Extraction finished" in caplog.text


def test_extract_supplier_products_fails_when_a_source_is_missing(
    cli_args: list[str], supplier_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    exit_code = cli.main([*cli_args, "extract-supplier-products"])

    assert exit_code == cli.EXIT_ERROR
    assert caplog.text.count("Supplier extraction failed") == 3


def test_validate_supplier_products_accepts_slightly_dirty_files(
    cli_args: list[str], supplier_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cli.main([*cli_args, "generate-sample-data", "--rows", "20"])

    exit_code = cli.main([*cli_args, "validate-supplier-products"])

    assert exit_code == cli.EXIT_OK
    assert "Validation finished" in caplog.text


def test_validate_supplier_products_fails_when_the_quality_gate_trips(
    cli_args: list[str], supplier_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cli.main([*cli_args, "generate-sample-data", "--rows", "40", "--bad-ratio", "0.6"])

    exit_code = cli.main([*cli_args, "validate-supplier-products"])

    assert exit_code == cli.EXIT_ERROR
    assert "Supplier validation failed" in caplog.text


def test_run_supplier_product_exits_zero_when_the_run_succeeds(
    cli_args: list[str], supplier_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakePool()
    monkeypatch.setattr(cli, "create_pool", lambda _config: fake)
    monkeypatch.setattr(
        cli,
        "run_supplier_product",
        lambda *_args, **_kwargs: RunSummary("run-1", RunStatus.SUCCEEDED, ()),
    )

    exit_code = cli.main([*cli_args, "run-supplier-product"])

    assert exit_code == cli.EXIT_OK
    assert fake.closed


@pytest.mark.parametrize("status", [RunStatus.PARTIAL, RunStatus.FAILED])
def test_run_supplier_product_exits_nonzero_when_suppliers_failed(
    cli_args: list[str],
    supplier_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: RunStatus,
) -> None:
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(
        cli, "run_supplier_product", lambda *_args, **_kwargs: RunSummary("run-1", status, ())
    )

    assert cli.main([*cli_args, "run-supplier-product"]) == cli.EXIT_ERROR


def test_run_customer_orders_exits_zero_when_the_run_succeeds(
    cli_args: list[str], orders_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakePool()
    monkeypatch.setattr(cli, "create_pool", lambda _config: fake)
    monkeypatch.setattr(
        cli,
        "run_customer_orders",
        lambda *_args, **_kwargs: OrdersRunSummary("run-1", RunStatus.SUCCEEDED),
    )

    assert cli.main([*cli_args, "run-customer-orders"]) == cli.EXIT_OK
    assert fake.closed


def test_run_customer_orders_exits_nonzero_when_the_run_failed(
    cli_args: list[str], orders_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(
        cli,
        "run_customer_orders",
        lambda *_args, **_kwargs: OrdersRunSummary("run-1", RunStatus.FAILED),
    )

    assert cli.main([*cli_args, "run-customer-orders"]) == cli.EXIT_ERROR


def test_generate_sample_orders_writes_the_file(
    cli_args: list[str], orders_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(
        cli, "known_product_ids", lambda _pool: [f"SUP-001:S1-{n:05d}" for n in range(1, 6)]
    )

    exit_code = cli.main([*cli_args, "generate-sample-orders", "--lines", "30"])

    assert exit_code == cli.EXIT_OK
    assert (orders_data_dir / "orders.csv").is_file()


def test_generate_sample_orders_needs_products_in_the_warehouse(
    cli_args: list[str],
    orders_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(cli, "known_product_ids", lambda _pool: [])

    exit_code = cli.main([*cli_args, "generate-sample-orders"])

    assert exit_code == cli.EXIT_ERROR
    assert "run run-supplier-product first" in caplog.text
    assert not (orders_data_dir / "orders.csv").exists()


def test_generate_sample_orders_rejects_a_bad_unknown_ratio(
    cli_args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([*cli_args, "generate-sample-orders", "--unknown-ratio", "2"])

    assert exit_info.value.code == 2
    assert "between 0 and 1" in capsys.readouterr().err


def test_run_inventory_exits_zero_when_the_run_succeeds(
    cli_args: list[str], inventory_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakePool()
    monkeypatch.setattr(cli, "create_pool", lambda _config: fake)
    monkeypatch.setattr(
        cli,
        "run_inventory",
        lambda *_args, **_kwargs: InventoryRunSummary("run-1", RunStatus.SUCCEEDED),
    )

    assert cli.main([*cli_args, "run-inventory"]) == cli.EXIT_OK
    assert fake.closed


def test_run_inventory_exits_nonzero_when_the_run_failed(
    cli_args: list[str], inventory_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(
        cli,
        "run_inventory",
        lambda *_args, **_kwargs: InventoryRunSummary("run-1", RunStatus.FAILED),
    )

    assert cli.main([*cli_args, "run-inventory"]) == cli.EXIT_ERROR


def _fake_serve(served: dict[str, object]) -> object:
    def serve(state: object, *, host: str, port: int, path: str) -> None:
        served.update(state=state, host=host, port=port, path=path)

    return serve


def test_serve_sample_inventory_serves_a_generated_feed(
    cli_args: list[str], inventory_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: dict[str, object] = {}
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(
        cli, "known_inventory_product_ids", lambda _pool: [f"SUP-001:S1-{n:05d}" for n in range(10)]
    )
    monkeypatch.setattr(cli, "serve_mock_feed", _fake_serve(served))

    exit_code = cli.main(
        [
            *cli_args,
            "serve-sample-inventory",
            "--port",
            "9999",
            "--locations",
            "2",
            "--coverage",
            "1",
            "--bad-ratio",
            "0",
            "--unknown-ratio",
            "0",
        ]
    )

    state = served["state"]
    assert exit_code == cli.EXIT_OK
    assert (served["host"], served["port"], served["path"]) == ("127.0.0.1", 9999, "/v1/stock")
    assert len(state.items) == 20  # type: ignore[attr-defined]
    assert state.token is None  # type: ignore[attr-defined]


def test_serve_sample_inventory_requires_the_configured_token(
    cli_args: list[str], inventory_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: dict[str, object] = {}
    monkeypatch.setenv("INVENTORY_API_TOKEN", "s3cret")
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(cli, "known_inventory_product_ids", lambda _pool: ["SUP-001:S1-00001"])
    monkeypatch.setattr(cli, "serve_mock_feed", _fake_serve(served))

    cli.main([*cli_args, "serve-sample-inventory"])
    token = served["state"].token  # type: ignore[attr-defined]
    assert token == "s3cret"  # noqa: S105


def test_serve_sample_inventory_needs_products_in_the_warehouse(
    cli_args: list[str],
    inventory_config: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    served: dict[str, object] = {}
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(cli, "known_inventory_product_ids", lambda _pool: [])
    monkeypatch.setattr(cli, "serve_mock_feed", _fake_serve(served))

    exit_code = cli.main([*cli_args, "serve-sample-inventory"])

    assert exit_code == cli.EXIT_ERROR
    assert "run run-supplier-product first" in caplog.text
    assert served == {}


@pytest.mark.parametrize("option", [["--port", "70000"], ["--coverage", "0"], ["--locations", "9"]])
def test_serve_sample_inventory_rejects_invalid_options(
    cli_args: list[str], option: list[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([*cli_args, "serve-sample-inventory", *option])

    assert exit_info.value.code == 2


def test_check_data_quality_exits_zero_without_failures(
    cli_args: list[str], quality_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakePool()
    monkeypatch.setattr(cli, "create_pool", lambda _config: fake)
    monkeypatch.setattr(
        cli,
        "run_quality_checks",
        lambda *_args, **_kwargs: _summary(CheckStatus.PASS, CheckStatus.WARN),
    )

    assert cli.main([*cli_args, "check-data-quality"]) == cli.EXIT_OK
    assert fake.closed


def test_check_data_quality_exits_nonzero_when_a_check_fails(
    cli_args: list[str], quality_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "create_pool", lambda _config: _FakePool())
    monkeypatch.setattr(
        cli, "run_quality_checks", lambda *_args, **_kwargs: _summary(CheckStatus.FAIL)
    )

    assert cli.main([*cli_args, "check-data-quality"]) == cli.EXIT_ERROR
