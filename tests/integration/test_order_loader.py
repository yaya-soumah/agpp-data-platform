from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import TupleRow

import agpp.pipelines.customer_orders.loading.loader as loader_module
from agpp.pipelines.customer_orders.loading import (
    LoadResult,
    RunStatus,
    finish_run,
    load_orders,
    record_failure,
    start_run,
)
from agpp.pipelines.customer_orders.models import OrderLine
from agpp.pipelines.customer_orders.transformation import to_rows
from agpp.pipelines.customer_orders.validation import ValidationResult
from agpp.shared.database import Pool, connection
from agpp.shared.database.warehouse import UpsertResult
from agpp.shared.database.warehouse import upsert as real_upsert
from agpp.shared.exceptions import (
    DatabaseConnectionError,
    InfrastructureError,
    SchemaValidationError,
    WarehouseWriteError,
)
from agpp.shared.resilience.retry import RetryPolicy
from agpp.shared.validation import RejectedRecord, RejectionStage

POLICY = RetryPolicy(max_attempts=3, initial_delay=0.0)
KNOWN_PRODUCT = "SUP-001:S1-00012"
UNKNOWN_PRODUCT = "SUP-001:S9-99999"
VALUES = {
    "order_id": "O-1001",
    "line_number": "1",
    "customer_id": "CUS-00042",
    "customer_name": "Marie Dupont",
    "customer_country": "LU",
    "ordered_at": "2026-11-09T10:00:00Z",
    "product_id": KNOWN_PRODUCT,
    "quantity": "2",
    "unit_price": "12.50",
    "currency": "EUR",
    "status": "placed",
    "updated_at": "2026-11-09T11:00:00Z",
}


def _no_sleep(_seconds: float) -> None:
    return None


def _line(**overrides: str) -> OrderLine:
    return OrderLine.model_validate({**VALUES, **overrides})


def _load(
    pool: Pool,
    lines: list[OrderLine],
    rejected: tuple[RejectedRecord, ...] = (),
    run_id: str = "run-1",
) -> LoadResult:
    start_run(pool, run_id)
    validation = ValidationResult("orders.csv", len(lines) + len(rejected), tuple(lines), rejected)
    return load_orders(
        pool,
        run_id=run_id,
        transformed=to_rows(lines),
        validation=validation,
        retry_policy=POLICY,
        sleep=_no_sleep,
    )


def _seed_product(pool: Pool, product_id: str = KNOWN_PRODUCT) -> int:
    """Insert a product the way the Supplier Product pipeline would have."""
    sku = product_id.split(":", 1)[1]
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.dim_supplier (supplier_id, supplier_name, country)"
            " VALUES ('SUP-001', 'Alpine Components', 'LU') ON CONFLICT (supplier_id) DO NOTHING"
        )
        row = conn.execute(
            "INSERT INTO warehouse.dim_product (product_id, supplier_key, supplier_sku,"
            " product_name, category, unit_price, currency, min_order_quantity, lead_time_days,"
            " is_active, source_updated_at)"
            " SELECT %s, supplier_key, %s, 'Hex Bolt', 'Fasteners', 10, 'EUR', 1, 5, true, now()"
            " FROM warehouse.dim_supplier WHERE supplier_id = 'SUP-001' RETURNING product_key",
            (product_id, sku),
        ).fetchone()
    assert row is not None
    return int(row[0])


def _lines(pool: Pool) -> list[tuple[Any, ...]]:
    with connection(pool) as conn:
        return conn.execute(
            "SELECT order_id, line_number, product_key, date_key, line_amount, status,"
            " source_updated_at, created_at, updated_at"
            " FROM warehouse.fact_order_line ORDER BY order_id, line_number"
        ).fetchall()


def _customers(pool: Pool) -> list[tuple[Any, ...]]:
    with connection(pool) as conn:
        return conn.execute(
            "SELECT customer_id, customer_name, country FROM warehouse.dim_customer"
            " WHERE customer_key > 0 ORDER BY customer_id"
        ).fetchall()


def _count(pool: Pool, query: str) -> int:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return int(row[0])


def test_a_first_load_writes_customers_and_lines(warehouse: Pool) -> None:
    product_key = _seed_product(warehouse)
    lines = [_line(), _line(line_number="2", product_id=UNKNOWN_PRODUCT)]

    result = _load(warehouse, lines)

    assert (result.lines_attempted, result.lines_written, result.lines_unchanged) == (2, 2, 0)
    assert result.customers_written == 1
    assert result.unknown_product_lines == 1
    assert _customers(warehouse) == [("CUS-00042", "Marie Dupont", "LU")]
    stored = _lines(warehouse)
    assert [(row[0], row[1], row[2]) for row in stored] == [
        ("O-1001", 1, product_key),
        ("O-1001", 2, -1),
    ]
    assert stored[0][3] == 20261109
    assert stored[0][4] == Decimal("25.0000")


def test_loading_the_same_data_again_changes_nothing(warehouse: Pool) -> None:
    _seed_product(warehouse)
    lines = [_line(), _line(line_number="2")]
    _load(warehouse, lines, run_id="run-1")
    before = _lines(warehouse)

    result = _load(warehouse, lines, run_id="run-2")

    assert (result.lines_written, result.lines_unchanged, result.customers_written) == (0, 2, 0)
    assert _lines(warehouse) == before


def test_an_unknown_product_is_healed_when_it_arrives(warehouse: Pool) -> None:
    lines = [_line()]
    first = _load(warehouse, lines, run_id="run-1")
    assert (first.unknown_product_lines, _lines(warehouse)[0][2]) == (1, -1)
    product_key = _seed_product(warehouse)

    second = _load(warehouse, lines, run_id="run-2")

    assert (second.lines_written, second.unknown_product_lines) == (1, 0)
    assert _lines(warehouse)[0][2] == product_key


def test_a_newer_update_changes_the_line(warehouse: Pool) -> None:
    _seed_product(warehouse)
    _load(warehouse, [_line()], run_id="run-1")

    shipped = _line(status="shipped", updated_at="2026-11-10T09:00:00Z")
    result = _load(warehouse, [shipped], run_id="run-2")

    assert result.lines_written == 1
    assert _lines(warehouse)[0][5] == "shipped"


def test_an_older_update_never_overwrites_newer_data(warehouse: Pool) -> None:
    _seed_product(warehouse)
    _load(warehouse, [_line(status="shipped", updated_at="2026-11-10T09:00:00Z")], run_id="run-1")

    stale = _line(status="cancelled", updated_at="2026-11-09T12:00:00Z")
    result = _load(warehouse, [stale], run_id="run-2")

    assert result.lines_written == 0
    assert _lines(warehouse)[0][5] == "shipped"


def test_a_newer_customer_name_wins_and_an_older_one_is_ignored(warehouse: Pool) -> None:
    _load(warehouse, [_line(customer_name="Marie Dupont")], run_id="run-1")

    _load(
        warehouse,
        [_line(customer_name="Marie Martin", updated_at="2026-11-10T09:00:00Z")],
        run_id="run-2",
    )
    assert _customers(warehouse)[0][1] == "Marie Martin"

    _load(
        warehouse,
        [_line(customer_name="Old Name", updated_at="2026-11-01T09:00:00Z")],
        run_id="run-3",
    )
    assert _customers(warehouse)[0][1] == "Marie Martin"


def test_rejects_and_the_run_result_are_recorded(warehouse: Pool) -> None:
    _seed_product(warehouse)
    rejected = (
        RejectedRecord(
            "orders.csv", 7, RejectionStage.PARSING, ("quantity: bad",), {"quantity": "x"}
        ),
    )

    result = _load(
        warehouse, [_line(), _line(line_number="2", product_id=UNKNOWN_PRODUCT)], rejected
    )

    assert result.rejects_stored == 1
    with connection(warehouse) as conn:
        reject_row = conn.execute(
            "SELECT pipeline, source_id, line_number FROM operational.rejected_records"
        ).fetchone()
        result_row = conn.execute(
            "SELECT status, rows_read, valid_rows, rejected_rows, lines_written,"
            " lines_unchanged, unknown_product_lines FROM operational.order_run_results"
        ).fetchone()
    assert reject_row == ("customer_orders", "orders.csv", 7)
    assert result_row == ("loaded", 3, 2, 1, 2, 0, 1)


def test_an_empty_file_loads_nothing_and_still_records_the_run(warehouse: Pool) -> None:
    result = _load(warehouse, [])

    assert (result.lines_attempted, result.lines_written) == (0, 0)
    assert _count(warehouse, "SELECT count(*) FROM operational.order_run_results") == 1


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


def test_a_failed_load_rolls_everything_back(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    boom = InfrastructureError("disk full", context={"sqlstate": "53100"})
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, _n: table == "fact_order_line", boom),
    )
    rejected = (RejectedRecord("orders.csv", 7, RejectionStage.PARSING, ("bad",), {}),)

    with pytest.raises(WarehouseWriteError) as info:
        _load(warehouse, [_line()], rejected)

    assert info.value.context == {"sqlstate": "53100"}
    assert _customers(warehouse) == []
    assert _count(warehouse, "SELECT count(*) FROM operational.rejected_records") == 0
    assert _count(warehouse, "SELECT count(*) FROM operational.order_run_results") == 0


def test_a_lost_connection_is_retried_and_data_is_written_once(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, n: table == "dim_customer" and n == 1, lost),
    )

    result = _load(warehouse, [_line(), _line(line_number="2")])

    assert result.lines_written == 2
    assert len(_customers(warehouse)) == 1


def test_a_connection_that_never_returns_raises_the_connection_error(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(loader_module, "upsert", _upsert_that_fails(lambda _t, _n: True, lost))

    with pytest.raises(DatabaseConnectionError):
        _load(warehouse, [_line()])

    assert _customers(warehouse) == []


def test_a_failure_is_recorded_with_its_stage(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    record_failure(warehouse, "run-1", SchemaValidationError("missing columns"))
    finish_run(warehouse, "run-1", RunStatus.FAILED)

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT status, failed_stage, error_message FROM operational.order_run_results"
        ).fetchone()
        run = conn.execute("SELECT status FROM operational.pipeline_runs").fetchone()
    assert row == ("failed", "validation", "missing columns")
    assert run == ("failed",)


def test_ordered_timestamps_are_kept(warehouse: Pool) -> None:
    _load(warehouse, [_line()])

    with connection(warehouse) as conn:
        row = conn.execute("SELECT ordered_at FROM warehouse.fact_order_line").fetchone()
    assert row == (datetime(2026, 11, 9, 10, 0, tzinfo=UTC),)
