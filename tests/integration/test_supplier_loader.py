from collections.abc import Callable
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import TupleRow

import agpp.pipelines.supplier_product.loading.loader as loader_module
from agpp.pipelines.supplier_product.loading import LoadResult, load_supplier, start_run
from agpp.pipelines.supplier_product.models import Supplier, SupplierProduct
from agpp.pipelines.supplier_product.transformation import transform_supplier
from agpp.pipelines.supplier_product.validation import (
    RejectedRecord,
    RejectionStage,
    ValidationResult,
)
from agpp.shared.database import Pool, connection
from agpp.shared.database.warehouse import UpsertResult
from agpp.shared.database.warehouse import upsert as real_upsert
from agpp.shared.exceptions import DatabaseConnectionError, InfrastructureError, WarehouseWriteError
from agpp.shared.resilience.retry import RetryPolicy

SUPPLIER = Supplier(supplier_id="SUP-001", name="Alpine Components", country="LU")
POLICY = RetryPolicy(max_attempts=3, initial_delay=0.0)
VALUES = {
    "supplier_id": "SUP-001",
    "supplier_sku": "A-1",
    "product_name": "Hex Bolt",
    "category": "Fasteners",
    "unit_price": "10.00",
    "currency": "EUR",
    "lead_time_days": "5",
    "updated_at": "2026-11-04T10:00:00Z",
}


def _no_sleep(_seconds: float) -> None:
    return None


def _product(sku: str, **overrides: str) -> SupplierProduct:
    return SupplierProduct.model_validate({**VALUES, "supplier_sku": sku, **overrides})


def _reject(line: int) -> RejectedRecord:
    return RejectedRecord(
        "SUP-001", line, RejectionStage.PARSING, ("unit_price: bad",), {"unit_price": "x"}
    )


def _load(
    pool: Pool,
    products: list[SupplierProduct],
    rejected: tuple[RejectedRecord, ...] = (),
    run_id: str = "run-1",
) -> LoadResult:
    start_run(pool, run_id)
    batch = transform_supplier(SUPPLIER, products)
    validation = ValidationResult(
        "SUP-001", len(products) + len(rejected), tuple(products), rejected
    )
    return load_supplier(
        pool,
        run_id=run_id,
        batch=batch,
        validation=validation,
        retry_policy=POLICY,
        sleep=_no_sleep,
    )


def _products(pool: Pool) -> list[tuple[object, ...]]:
    with connection(pool) as conn:
        return conn.execute(
            "SELECT * FROM warehouse.dim_product WHERE product_key > 0 ORDER BY product_id"
        ).fetchall()


def _count(pool: Pool, table: str) -> int:
    queries = {
        "suppliers": "SELECT count(*) FROM warehouse.dim_supplier WHERE supplier_key > 0",
        "rejects": "SELECT count(*) FROM operational.rejected_records",
        "results": "SELECT count(*) FROM operational.supplier_run_results",
    }
    with connection(pool) as conn:
        row = conn.execute(queries[table]).fetchone()
    assert row is not None
    return int(row[0])


def test_a_first_load_writes_everything(warehouse: Pool) -> None:
    result = _load(warehouse, [_product("A-1"), _product("A-2")], (_reject(7),))

    assert (result.products_attempted, result.products_written, result.products_unchanged) == (
        2,
        2,
        0,
    )
    assert result.rejects_stored == 1
    assert _count(warehouse, "suppliers") == 1
    assert len(_products(warehouse)) == 2
    assert _count(warehouse, "rejects") == 1
    assert _count(warehouse, "results") == 1


def test_products_point_at_their_supplier(warehouse: Pool) -> None:
    _load(warehouse, [_product("A-1"), _product("A-2")])

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT count(*) FROM warehouse.dim_product AS p"
            " JOIN warehouse.dim_supplier AS s USING (supplier_key)"
            " WHERE s.supplier_id = 'SUP-001' AND p.product_key > 0"
        ).fetchone()
    assert row == (2,)


def test_the_run_result_is_recorded_with_counts(warehouse: Pool) -> None:
    _load(warehouse, [_product("A-1"), _product("A-2")], (_reject(7),))

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT status, failed_stage, rows_read, valid_rows, rejected_rows,"
            " products_written, products_unchanged FROM operational.supplier_run_results"
        ).fetchone()
    assert row == ("loaded", None, 3, 2, 1, 2, 0)


def test_loading_the_same_data_again_changes_nothing(warehouse: Pool) -> None:
    products = [_product("A-1"), _product("A-2")]
    _load(warehouse, products, run_id="run-1")
    before = _products(warehouse)

    result = _load(warehouse, products, run_id="run-2")

    assert (result.products_written, result.products_unchanged) == (0, 2)
    assert _products(warehouse) == before


def test_only_changed_products_are_updated(warehouse: Pool) -> None:
    _load(warehouse, [_product("A-1"), _product("A-2")], run_id="run-1")
    before = _products(warehouse)

    changed = _product("A-2", unit_price="12.00", updated_at="2026-11-05T09:00:00Z")
    result = _load(warehouse, [_product("A-1"), changed], run_id="run-2")

    after = _products(warehouse)
    assert result.products_written == 1
    assert after[0] == before[0]
    assert after[1] != before[1]


def test_older_data_does_not_overwrite_newer_data(warehouse: Pool) -> None:
    _load(warehouse, [_product("A-1", product_name="Newer")], run_id="run-1")

    stale = _product("A-1", product_name="Older", updated_at="2026-11-01T10:00:00Z")
    result = _load(warehouse, [stale], run_id="run-2")

    assert result.products_written == 0
    assert _products(warehouse)[0][4] == "Newer"


def test_equal_timestamps_still_apply_a_correction(warehouse: Pool) -> None:
    _load(warehouse, [_product("A-1", product_name="Typo")], run_id="run-1")

    fixed = _product("A-1", product_name="Fixed")
    result = _load(warehouse, [fixed], run_id="run-2")

    assert result.products_written == 1
    assert _products(warehouse)[0][4] == "Fixed"


def test_the_same_run_does_not_store_rejects_twice(warehouse: Pool) -> None:
    _load(warehouse, [_product("A-1")], (_reject(7),), run_id="run-1")

    result = _load(warehouse, [_product("A-1")], (_reject(7),), run_id="run-1")

    assert result.rejects_stored == 0
    assert _count(warehouse, "rejects") == 1
    assert _count(warehouse, "results") == 1


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
        loader_module, "upsert", _upsert_that_fails(lambda table, _n: table == "dim_product", boom)
    )

    with pytest.raises(WarehouseWriteError) as info:
        _load(warehouse, [_product("A-1")], (_reject(7),))

    assert info.value.context == {"supplier_id": "SUP-001", "sqlstate": "53100"}
    assert info.value.retryable is False
    assert _count(warehouse, "suppliers") == 0
    assert _count(warehouse, "rejects") == 0
    assert _count(warehouse, "results") == 0


def test_a_lost_connection_is_retried_and_data_is_written_once(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, n: table == "dim_supplier" and n == 1, lost),
    )

    result = _load(warehouse, [_product("A-1"), _product("A-2")])

    assert result.products_written == 2
    assert _count(warehouse, "suppliers") == 1
    assert len(_products(warehouse)) == 2


def test_a_connection_that_never_returns_raises_the_connection_error(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(loader_module, "upsert", _upsert_that_fails(lambda _table, _n: True, lost))

    with pytest.raises(DatabaseConnectionError):
        _load(warehouse, [_product("A-1")])

    assert _count(warehouse, "suppliers") == 0
