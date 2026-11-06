import csv
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import TupleRow

import agpp.pipelines.supplier_product.loading.loader as loader_module
import agpp.pipelines.supplier_product.service as service_module
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.loading import RunStatus
from agpp.pipelines.supplier_product.sample_data import COLUMNS, generate_supplier_files
from agpp.pipelines.supplier_product.service import RunSummary, run_supplier_product
from agpp.shared.database import Pool, connection
from agpp.shared.database.warehouse import UpsertResult
from agpp.shared.database.warehouse import upsert as real_upsert
from agpp.shared.exceptions import DatabaseConnectionError, InfrastructureError

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
GOOD_ROW = {
    "supplier_sku": "TEST-001",
    "product_name": "Test Product",
    "category": "Testing",
    "unit_price": "10.00",
    "currency": "EUR",
    "min_order_quantity": "1",
    "lead_time_days": "5",
    "is_active": "true",
    "updated_at": "2026-11-04T10:00:00Z",
}


def _no_sleep(_seconds: float) -> None:
    return None


@pytest.fixture
def config(tmp_path: Path) -> SupplierProductConfig:
    def supplier(number: str, delimiter: str) -> dict[str, object]:
        return {
            "supplier_id": f"SUP-{number}",
            "name": f"Supplier {number}",
            "country": "LU",
            "source": {
                "type": "csv",
                "path": str(tmp_path / f"{number}.csv"),
                "delimiter": delimiter,
            },
        }

    return SupplierProductConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.1,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_unit_price": 1000000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "loading": {"max_attempts": 3, "initial_delay_seconds": 0},
            "suppliers": [supplier("001", ","), supplier("002", ";")],
        }
    )


@pytest.fixture
def first_file(config: SupplierProductConfig) -> Path:
    """Generate the sample files and add one known-good product to SUP-001's file."""
    generate_supplier_files(config, rows_per_supplier=100, bad_row_ratio=0.05, seed=21, now=NOW)
    path = Path(config.suppliers[0].source.path)
    _edit_rows(path, ",", lambda rows: [*rows, dict(GOOD_ROW)])
    return path


def _edit_rows(
    path: Path, delimiter: str, edit: Callable[[list[dict[str, str]]], list[dict[str, str]]]
) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=delimiter))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(edit(rows))


def _change_test_row(path: Path, **changes: str) -> None:
    def edit(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        return [{**row, **changes} if row["supplier_sku"] == "TEST-001" else row for row in rows]

    _edit_rows(path, ",", edit)


def _run(pool: Pool, config: SupplierProductConfig, run_id: str) -> RunSummary:
    return run_supplier_product(pool, config, run_id=run_id, now=NOW, sleep=_no_sleep)


def _rows(pool: Pool, table: str) -> list[tuple[Any, ...]]:
    queries = {
        "suppliers": "SELECT * FROM warehouse.dim_supplier WHERE supplier_key > 0"
        " ORDER BY supplier_key",
        "products": "SELECT * FROM warehouse.dim_product WHERE product_key > 0"
        " ORDER BY product_key",
    }
    with connection(pool) as conn:
        return conn.execute(queries[table]).fetchall()


def _scalar(pool: Pool, query: str, params: tuple[object, ...] = ()) -> Any:
    with connection(pool) as conn:
        row = conn.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def _upsert_that_fails(
    when: Callable[[str, int], bool], error: Exception
) -> Callable[..., UpsertResult]:
    calls: dict[str, int] = {}

    def wrapper(conn: Connection[TupleRow], **kwargs: Any) -> UpsertResult:
        table = kwargs["table"]
        calls[table] = calls.get(table, 0) + 1
        if when(table, calls[table]):
            raise error
        return real_upsert(conn, **kwargs)

    return wrapper


def test_a_first_run_loads_every_supplier(
    warehouse: Pool, config: SupplierProductConfig, first_file: Path
) -> None:
    summary = _run(warehouse, config, "run-1")

    assert summary.status is RunStatus.SUCCEEDED
    loads = [outcome.load for outcome in summary.outcomes if outcome.load]
    assert len(loads) == 2
    assert len(_rows(warehouse, "suppliers")) == 2
    assert len(_rows(warehouse, "products")) == sum(load.products_written for load in loads)
    assert len(_rows(warehouse, "products")) > 100
    stored = _scalar(warehouse, "SELECT count(*) FROM operational.rejected_records")
    assert stored == sum(load.rejects_stored for load in loads) > 0
    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "succeeded"
    assert _scalar(warehouse, "SELECT finished_at IS NOT NULL FROM operational.pipeline_runs")
    assert _scalar(warehouse, "SELECT count(*) FROM operational.supplier_run_results") == 2


def test_running_the_pipeline_twice_leaves_the_warehouse_unchanged(
    warehouse: Pool, config: SupplierProductConfig, first_file: Path
) -> None:
    first = _run(warehouse, config, "run-1")
    suppliers_before = _rows(warehouse, "suppliers")
    products_before = _rows(warehouse, "products")

    second = _run(warehouse, config, "run-2")

    assert second.status is RunStatus.SUCCEEDED
    assert _rows(warehouse, "suppliers") == suppliers_before
    assert _rows(warehouse, "products") == products_before
    assert all(o.load and o.load.products_written == 0 for o in second.outcomes)
    assert all(o.load and o.load.products_unchanged > 0 for o in second.outcomes)
    first_rejects = sum(o.load.rejects_stored for o in first.outcomes if o.load)
    second_rejects = sum(o.load.rejects_stored for o in second.outcomes if o.load)
    assert first_rejects == second_rejects  # rejects are history, kept per run
    assert _scalar(warehouse, "SELECT count(*) FROM operational.pipeline_runs") == 2


def test_a_changed_price_updates_only_that_product(
    warehouse: Pool, config: SupplierProductConfig, first_file: Path
) -> None:
    _run(warehouse, config, "run-1")
    before = _rows(warehouse, "products")
    _change_test_row(first_file, unit_price="999.99", updated_at="2026-11-05T12:01:00Z")

    second = _run(warehouse, config, "run-2")

    after = _rows(warehouse, "products")
    changed = [row for row in after if row[1] == "SUP-001:TEST-001"]
    assert changed[0][6] == Decimal("999.99")
    assert [row for row in after if row[1] != "SUP-001:TEST-001"] == [
        row for row in before if row[1] != "SUP-001:TEST-001"
    ]
    written = [o.load.products_written for o in second.outcomes if o.load]
    assert written == [1, 0]


def test_a_late_older_file_does_not_overwrite_newer_data(
    warehouse: Pool, config: SupplierProductConfig, first_file: Path
) -> None:
    _run(warehouse, config, "run-1")
    _change_test_row(first_file, product_name="STALE", updated_at="2020-01-01T00:00:00Z")

    second = _run(warehouse, config, "run-2")

    name = _scalar(
        warehouse,
        "SELECT product_name FROM warehouse.dim_product WHERE product_id = 'SUP-001:TEST-001'",
    )
    assert name == "Test Product"
    assert all(o.load and o.load.products_written == 0 for o in second.outcomes)


def test_a_missing_file_fails_only_that_supplier(
    warehouse: Pool, config: SupplierProductConfig, first_file: Path
) -> None:
    Path(config.suppliers[1].source.path).unlink()

    summary = _run(warehouse, config, "run-1")

    assert summary.status is RunStatus.PARTIAL
    assert [o.succeeded for o in summary.outcomes] == [True, False]
    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "partial"
    failed = _scalar(
        warehouse,
        "SELECT failed_stage FROM operational.supplier_run_results WHERE supplier_id = 'SUP-002'",
    )
    assert failed == "extraction"
    assert [row[1] for row in _rows(warehouse, "suppliers")] == ["SUP-001"]


def test_a_file_that_fails_the_quality_gate_loads_nothing(
    warehouse: Pool, config: SupplierProductConfig, first_file: Path
) -> None:
    bad_rows = [{**GOOD_ROW, "supplier_sku": f"B-{n}", "unit_price": "0"} for n in range(10)]
    _edit_rows(Path(config.suppliers[1].source.path), ";", lambda _rows: bad_rows)

    summary = _run(warehouse, config, "run-1")

    assert summary.status is RunStatus.PARTIAL
    stage = _scalar(
        warehouse,
        "SELECT failed_stage FROM operational.supplier_run_results WHERE supplier_id = 'SUP-002'",
    )
    assert stage == "validation"
    count = _scalar(
        warehouse, "SELECT count(*) FROM warehouse.dim_supplier WHERE supplier_id = 'SUP-002'"
    )
    assert count == 0
    assert all(row[1].startswith("SUP-001:") for row in _rows(warehouse, "products"))


def test_a_failed_write_rolls_back_only_that_supplier(
    warehouse: Pool,
    config: SupplierProductConfig,
    first_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boom = InfrastructureError("disk full", context={"sqlstate": "53100"})
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, n: table == "dim_product" and n == 2, boom),
    )

    summary = _run(warehouse, config, "run-1")

    assert summary.status is RunStatus.PARTIAL
    assert [row[1] for row in _rows(warehouse, "suppliers")] == ["SUP-001"]
    stage = _scalar(
        warehouse,
        "SELECT failed_stage FROM operational.supplier_run_results WHERE supplier_id = 'SUP-002'",
    )
    assert stage == "loading"


def test_every_supplier_failing_makes_the_run_failed(
    warehouse: Pool,
    config: SupplierProductConfig,
    first_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boom = InfrastructureError("disk full", context={"sqlstate": "53100"})
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, _n: table == "dim_product", boom),
    )

    summary = _run(warehouse, config, "run-1")

    assert summary.status is RunStatus.FAILED
    assert _rows(warehouse, "suppliers") == []
    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "failed"


def test_a_lost_connection_is_retried_and_the_run_succeeds(
    warehouse: Pool,
    config: SupplierProductConfig,
    first_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, n: table == "dim_supplier" and n == 1, lost),
    )

    summary = _run(warehouse, config, "run-1")

    assert summary.status is RunStatus.SUCCEEDED
    assert len(_rows(warehouse, "suppliers")) == 2


def test_an_unexpected_error_marks_the_run_failed_and_propagates(
    warehouse: Pool,
    config: SupplierProductConfig,
    first_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(service_module, "extract_all", broken)

    with pytest.raises(RuntimeError, match="bug"):
        _run(warehouse, config, "run-1")

    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "failed"
    assert _scalar(warehouse, "SELECT finished_at IS NOT NULL FROM operational.pipeline_runs")
