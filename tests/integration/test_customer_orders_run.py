from datetime import UTC, datetime
from pathlib import Path
from typing import Any, LiteralString

import pytest

import agpp.pipelines.customer_orders.service as service_module
from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.loading import RunStatus
from agpp.pipelines.customer_orders.sample_data import (
    GenerationSummary,
    generate_orders_file,
    known_product_ids,
)
from agpp.pipelines.customer_orders.service import RunSummary, run_customer_orders
from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.sample_data import generate_supplier_files
from agpp.pipelines.supplier_product.service import run_supplier_product
from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import (
    QualityThresholdExceededError,
    SchemaValidationError,
    SourceUnavailableError,
)

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
PRODUCTS = [f"SUP-001:S1-{number:05d}" for number in range(1, 21)]


def _no_sleep(_seconds: float) -> None:
    return None


@pytest.fixture
def config(tmp_path: Path) -> CustomerOrdersConfig:
    return CustomerOrdersConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.05,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_line_amount": 1000000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "loading": {"max_attempts": 3, "initial_delay_seconds": 0},
            "source": {"type": "csv", "path": str(tmp_path / "orders.csv")},
        }
    )


def _seed_products(pool: Pool, product_ids: list[str]) -> None:
    """Insert products the way the Supplier Product pipeline would have."""
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.dim_supplier (supplier_id, supplier_name, country)"
            " VALUES ('SUP-001', 'Alpine Components', 'LU') ON CONFLICT (supplier_id) DO NOTHING"
        )
        for product_id in product_ids:
            conn.execute(
                "INSERT INTO warehouse.dim_product (product_id, supplier_key, supplier_sku,"
                " product_name, category, unit_price, currency, min_order_quantity,"
                " lead_time_days, is_active, source_updated_at)"
                " SELECT %s, supplier_key, %s, 'Hex Bolt', 'Fasteners', 10, 'EUR', 1, 5, true,"
                " now() FROM warehouse.dim_supplier WHERE supplier_id = 'SUP-001'",
                (product_id, product_id.split(":", 1)[1]),
            )


def _generate(
    config: CustomerOrdersConfig,
    *,
    lines: int = 200,
    bad: float = 0.04,
    unknown: float = 0.0,
    seed: int = 1,
    product_ids: list[str] | None = None,
) -> GenerationSummary:
    return generate_orders_file(
        config,
        product_ids=PRODUCTS if product_ids is None else product_ids,
        lines=lines,
        bad_row_ratio=bad,
        unknown_product_ratio=unknown,
        seed=seed,
        now=NOW,
    )


def _run(pool: Pool, config: CustomerOrdersConfig, run_id: str = "run-1") -> RunSummary:
    return run_customer_orders(pool, config, run_id=run_id, now=NOW, sleep=_no_sleep)


def _scalar(pool: Pool, query: LiteralString) -> Any:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


def _snapshot(pool: Pool, which: str) -> list[tuple[Any, ...]]:
    queries: dict[str, LiteralString] = {
        "lines": "SELECT * FROM warehouse.fact_order_line ORDER BY order_id, line_number",
        "customers": "SELECT * FROM warehouse.dim_customer WHERE customer_key > 0"
        " ORDER BY customer_key",
    }
    with connection(pool) as conn:
        return conn.execute(queries[which]).fetchall()


def test_a_first_run_loads_the_file(warehouse: Pool, config: CustomerOrdersConfig) -> None:
    _seed_products(warehouse, PRODUCTS)
    generated = _generate(config)

    summary = _run(warehouse, config)

    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load is not None
    load = summary.load
    assert load.lines_attempted + load.rejects_stored == generated.rows
    assert 0 < load.rejects_stored <= generated.defective_rows
    assert load.unknown_product_lines == 0
    assert (
        _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line") == load.lines_written
    )
    customers = _scalar(
        warehouse, "SELECT count(*) FROM warehouse.dim_customer WHERE customer_key > 0"
    )
    assert customers == load.customers_written > 0
    assert (
        _scalar(warehouse, "SELECT count(*) FROM operational.rejected_records")
        == load.rejects_stored
    )
    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "succeeded"
    assert _scalar(warehouse, "SELECT status FROM operational.order_run_results") == "loaded"


def test_running_the_pipeline_twice_leaves_the_warehouse_unchanged(
    warehouse: Pool, config: CustomerOrdersConfig
) -> None:
    _seed_products(warehouse, PRODUCTS)
    _generate(config)
    first = _run(warehouse, config, "run-1")
    lines_before = _snapshot(warehouse, "lines")
    customers_before = _snapshot(warehouse, "customers")

    second = _run(warehouse, config, "run-2")

    assert second.status is RunStatus.SUCCEEDED
    assert second.load is not None
    assert first.load is not None
    assert (second.load.lines_written, second.load.customers_written) == (0, 0)
    assert second.load.lines_unchanged == first.load.lines_written
    assert _snapshot(warehouse, "lines") == lines_before
    assert _snapshot(warehouse, "customers") == customers_before
    assert second.load.rejects_stored == first.load.rejects_stored  # history is kept per run
    assert _scalar(warehouse, "SELECT count(*) FROM operational.pipeline_runs") == 2


def test_lines_with_unknown_products_are_healed_when_the_catalog_arrives(
    warehouse: Pool, config: CustomerOrdersConfig
) -> None:
    _seed_products(warehouse, PRODUCTS[:10])
    _generate(config, bad=0.0)
    first = _run(warehouse, config, "run-1")
    assert first.load is not None
    assert first.load.unknown_product_lines > 0
    unknown_lines = first.load.unknown_product_lines
    assert (
        _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line WHERE product_key = -1")
        == unknown_lines
    )

    _seed_products(warehouse, PRODUCTS[10:])
    second = _run(warehouse, config, "run-2")

    assert second.load is not None
    assert second.load.unknown_product_lines == 0
    assert second.load.lines_written == unknown_lines
    assert (
        _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line WHERE product_key = -1")
        == 0
    )


def test_orders_load_even_when_the_catalog_is_empty(
    warehouse: Pool, config: CustomerOrdersConfig
) -> None:
    _generate(config, lines=100, bad=0.0)

    summary = _run(warehouse, config)

    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load is not None
    assert summary.load.unknown_product_lines == summary.load.lines_written == 100


def test_a_missing_file_fails_the_run_and_loads_nothing(
    warehouse: Pool, config: CustomerOrdersConfig
) -> None:
    summary = _run(warehouse, config)

    assert summary.status is RunStatus.FAILED
    assert isinstance(summary.error, SourceUnavailableError)
    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "failed"
    assert (
        _scalar(warehouse, "SELECT failed_stage FROM operational.order_run_results") == "extraction"
    )
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line") == 0


def test_a_file_with_a_missing_column_fails_validation(
    warehouse: Pool, config: CustomerOrdersConfig
) -> None:
    columns = [name for name in REQUIRED_COLUMNS if name != "status"]
    Path(config.source.path).write_text(",".join(columns) + "\n", encoding="utf-8")

    summary = _run(warehouse, config)

    assert summary.status is RunStatus.FAILED
    assert isinstance(summary.error, SchemaValidationError)
    assert (
        _scalar(warehouse, "SELECT failed_stage FROM operational.order_run_results") == "validation"
    )


def test_a_file_that_fails_the_quality_gate_loads_nothing_and_a_fixed_file_recovers(
    warehouse: Pool, config: CustomerOrdersConfig
) -> None:
    _seed_products(warehouse, PRODUCTS)
    _generate(config, lines=100, bad=0.5)

    failed = _run(warehouse, config, "run-1")

    assert failed.status is RunStatus.FAILED
    assert isinstance(failed.error, QualityThresholdExceededError)
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line") == 0
    assert (
        _scalar(warehouse, "SELECT count(*) FROM warehouse.dim_customer WHERE customer_key > 0")
        == 0
    )

    _generate(config, lines=100, bad=0.0)
    recovered = _run(warehouse, config, "run-2")

    assert recovered.status is RunStatus.SUCCEEDED
    assert _scalar(warehouse, "SELECT count(*) FROM operational.order_run_results") == 2
    assert _scalar(warehouse, "SELECT count(*) FROM warehouse.fact_order_line") == 100


def test_an_unexpected_error_marks_the_run_failed_and_propagates(
    warehouse: Pool, config: CustomerOrdersConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(service_module, "extract_orders", broken)

    with pytest.raises(RuntimeError, match="bug"):
        _run(warehouse, config)

    assert _scalar(warehouse, "SELECT status FROM operational.pipeline_runs") == "failed"
    assert _scalar(warehouse, "SELECT finished_at IS NOT NULL FROM operational.pipeline_runs")


def test_known_product_ids_lists_catalog_products_only(warehouse: Pool) -> None:
    _seed_products(warehouse, PRODUCTS[:3])

    assert known_product_ids(warehouse) == PRODUCTS[:3]


def test_both_pipelines_share_one_warehouse(
    warehouse: Pool, config: CustomerOrdersConfig, tmp_path: Path
) -> None:
    supplier_config = SupplierProductConfig.model_validate(
        {
            "quality": {
                "max_reject_ratio": 0.1,
                "allowed_currencies": ["EUR", "USD", "GBP", "CHF"],
                "max_unit_price": 1000000,
                "future_tolerance_minutes": 5,
            },
            "extraction": {"max_attempts": 1, "initial_delay_seconds": 0},
            "loading": {"max_attempts": 1, "initial_delay_seconds": 0},
            "suppliers": [
                {
                    "supplier_id": "SUP-001",
                    "name": "Alpine Components",
                    "country": "LU",
                    "source": {"type": "csv", "path": str(tmp_path / "suppliers.csv")},
                }
            ],
        }
    )
    generate_supplier_files(
        supplier_config, rows_per_supplier=50, bad_row_ratio=0.0, seed=3, now=NOW
    )
    supplier_summary = run_supplier_product(
        warehouse, supplier_config, run_id="supplier-run", now=NOW, sleep=_no_sleep
    )
    assert supplier_summary.status is RunStatus.SUCCEEDED
    product_ids = known_product_ids(warehouse)
    assert len(product_ids) == 50

    _generate(config, lines=100, bad=0.0, product_ids=product_ids)
    summary = _run(warehouse, config, "orders-run")

    assert summary.status is RunStatus.SUCCEEDED
    assert summary.load is not None
    assert summary.load.unknown_product_lines == 0
    joined = _scalar(
        warehouse,
        "SELECT count(*) FROM warehouse.fact_order_line AS f"
        " JOIN warehouse.dim_product AS p USING (product_key)"
        " JOIN warehouse.dim_customer AS c USING (customer_key)"
        " JOIN warehouse.dim_date AS d USING (date_key)"
        " WHERE p.product_key > 0 AND c.customer_key > 0",
    )
    assert joined == 100
    assert _scalar(warehouse, "SELECT count(DISTINCT pipeline) FROM operational.pipeline_runs") == 2
