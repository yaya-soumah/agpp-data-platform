from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, LiteralString

import pytest
from psycopg import Connection
from psycopg.rows import TupleRow

import agpp.pipelines.inventory.loading.loader as loader_module
from agpp.pipelines.inventory.loading import (
    LoadResult,
    RunStatus,
    finish_run,
    load_inventory,
    record_failure,
    start_run,
)
from agpp.pipelines.inventory.models import InventoryItem
from agpp.pipelines.inventory.transformation import to_rows
from agpp.pipelines.inventory.validation import ValidationResult
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
SNAPSHOT = datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
KNOWN_PRODUCT = "SUP-001:S1-00012"
UNKNOWN_PRODUCT = "SUP-001:S9-99999"
VALUES = {
    "location_code": "LU-01",
    "location_name": "Luxembourg Warehouse",
    "location_country": "LU",
    "product_id": KNOWN_PRODUCT,
    "on_hand": "120",
    "reserved": "20",
    "reorder_point": "50",
    "updated_at": "2026-11-13T05:30:00Z",
}


def _no_sleep(_seconds: float) -> None:
    return None


def _item(**overrides: str) -> InventoryItem:
    return InventoryItem.model_validate({**VALUES, **overrides})


def _load(
    pool: Pool,
    items: list[InventoryItem],
    rejected: tuple[RejectedRecord, ...] = (),
    run_id: str = "run-1",
    snapshot_at: datetime = SNAPSHOT,
) -> LoadResult:
    start_run(pool, run_id)
    validation = ValidationResult(
        source_id="feed",
        snapshot_at=snapshot_at,
        rows_read=len(items) + len(rejected),
        valid=tuple(items),
        rejected=rejected,
    )
    return load_inventory(
        pool,
        run_id=run_id,
        transformed=to_rows(snapshot_at, items),
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


def _rows(pool: Pool) -> list[tuple[Any, ...]]:
    with connection(pool) as conn:
        return conn.execute(
            "SELECT l.location_code, f.product_id, f.product_key, f.date_key, f.on_hand,"
            " f.available, f.below_reorder_point, f.snapshot_at, f.created_at, f.updated_at"
            " FROM warehouse.fact_inventory_snapshot AS f"
            " JOIN warehouse.dim_location AS l USING (location_key)"
            " ORDER BY f.date_key, l.location_code, f.product_id"
        ).fetchall()


def _locations(pool: Pool) -> list[tuple[Any, ...]]:
    with connection(pool) as conn:
        return conn.execute(
            "SELECT location_code, location_name, country FROM warehouse.dim_location"
            " WHERE location_key > 0 ORDER BY location_code"
        ).fetchall()


def _count(pool: Pool, query: LiteralString) -> int:
    with connection(pool) as conn:
        row = conn.execute(query).fetchone()
    assert row is not None
    return int(row[0])


def test_a_first_load_writes_locations_and_rows(warehouse: Pool) -> None:
    product_key = _seed_product(warehouse)
    items = [
        _item(),
        _item(location_code="LU-02", product_id=UNKNOWN_PRODUCT, on_hand="10", reserved="0"),
    ]

    result = _load(warehouse, items)

    assert (result.rows_attempted, result.rows_written, result.rows_unchanged) == (2, 2, 0)
    assert (result.locations_written, result.unknown_product_rows) == (2, 1)
    assert result.below_reorder_rows == 1
    rows = _rows(warehouse)
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        ("LU-01", KNOWN_PRODUCT, product_key, 20261113),
        ("LU-02", UNKNOWN_PRODUCT, -1, 20261113),
    ]
    assert [(r[4], r[5], r[6]) for r in rows] == [(120, 100, False), (10, 10, True)]
    assert len(_locations(warehouse)) == 2


def test_loading_the_same_feed_again_changes_nothing(warehouse: Pool) -> None:
    _seed_product(warehouse)
    items = [_item(), _item(product_id="SUP-001:S1-00013")]
    _load(warehouse, items, run_id="run-1")
    before = _rows(warehouse)

    result = _load(warehouse, items, run_id="run-2")

    assert (result.rows_written, result.rows_unchanged, result.locations_written) == (0, 2, 0)
    assert _rows(warehouse) == before


def test_a_later_snapshot_of_the_same_day_replaces_the_row(warehouse: Pool) -> None:
    _load(warehouse, [_item()], run_id="run-1")
    later = datetime(2026, 11, 13, 18, 0, tzinfo=UTC)

    result = _load(
        warehouse,
        [_item(on_hand="90", updated_at="2026-11-13T17:30:00Z")],
        run_id="run-2",
        snapshot_at=later,
    )

    rows = _rows(warehouse)
    assert result.rows_written == 1
    assert len(rows) == 1
    assert (rows[0][4], rows[0][7]) == (90, later)


def test_an_older_snapshot_arriving_late_never_overwrites_a_newer_one(warehouse: Pool) -> None:
    later = datetime(2026, 11, 13, 18, 0, tzinfo=UTC)
    _load(warehouse, [_item(on_hand="90")], run_id="run-1", snapshot_at=later)

    result = _load(warehouse, [_item(on_hand="120")], run_id="run-2", snapshot_at=SNAPSHOT)

    assert result.rows_written == 0
    assert _rows(warehouse)[0][4] == 90


def test_the_next_day_adds_rows_and_keeps_the_history(warehouse: Pool) -> None:
    _load(warehouse, [_item()], run_id="run-1")
    next_day = datetime(2026, 11, 14, 6, 0, tzinfo=UTC)

    result = _load(
        warehouse,
        [_item(on_hand="100", updated_at="2026-11-14T05:30:00Z")],
        run_id="run-2",
        snapshot_at=next_day,
    )

    rows = _rows(warehouse)
    assert result.rows_written == 1
    assert [(r[3], r[4]) for r in rows] == [(20261113, 120), (20261114, 100)]


def test_unknown_products_stay_distinct_and_are_healed_when_the_catalog_arrives(
    warehouse: Pool,
) -> None:
    items = [_item(product_id="SUP-001:S9-00001"), _item(product_id="SUP-001:S9-00002")]
    first = _load(warehouse, items, run_id="run-1")
    assert (first.unknown_product_rows, len(_rows(warehouse))) == (2, 2)
    assert {row[2] for row in _rows(warehouse)} == {-1}
    keys = {
        "SUP-001:S9-00001": _seed_product(warehouse, "SUP-001:S9-00001"),
        "SUP-001:S9-00002": _seed_product(warehouse, "SUP-001:S9-00002"),
    }

    second = _load(warehouse, items, run_id="run-2")

    assert (second.rows_written, second.unknown_product_rows) == (2, 0)
    assert {row[1]: row[2] for row in _rows(warehouse)} == keys


def test_a_newer_location_name_wins_and_an_older_one_is_ignored(warehouse: Pool) -> None:
    _load(warehouse, [_item()], run_id="run-1")

    _load(
        warehouse,
        [_item(location_name="Luxembourg Hub", updated_at="2026-11-13T05:45:00Z")],
        run_id="run-2",
    )
    assert _locations(warehouse)[0][1] == "Luxembourg Hub"

    _load(
        warehouse,
        [_item(location_name="Old Name", updated_at="2026-11-01T05:45:00Z")],
        run_id="run-3",
    )
    assert _locations(warehouse)[0][1] == "Luxembourg Hub"


def test_rejects_and_the_run_result_are_recorded(warehouse: Pool) -> None:
    _seed_product(warehouse)
    rejected = (
        RejectedRecord("feed", 3, RejectionStage.PARSING, ("on_hand: bad",), {"on_hand": "x"}),
    )
    items = [_item(), _item(product_id=UNKNOWN_PRODUCT, on_hand="10", reserved="0")]

    result = _load(warehouse, items, rejected)

    assert result.rejects_stored == 1
    with connection(warehouse) as conn:
        reject_row = conn.execute(
            "SELECT pipeline, source_id, line_number FROM operational.rejected_records"
        ).fetchone()
        result_row = conn.execute(
            "SELECT status, snapshot_at, rows_read, valid_rows, rejected_rows, rows_written,"
            " rows_unchanged, unknown_product_rows, below_reorder_rows"
            " FROM operational.inventory_run_results"
        ).fetchone()
    assert reject_row == ("inventory", "feed", 3)
    assert result_row == ("loaded", SNAPSHOT, 3, 2, 1, 2, 0, 1, 1)


def test_an_empty_feed_loads_nothing_and_still_records_the_run(warehouse: Pool) -> None:
    result = _load(warehouse, [])

    assert (result.rows_attempted, result.rows_written) == (0, 0)
    assert _count(warehouse, "SELECT count(*) FROM operational.inventory_run_results") == 1


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
        _upsert_that_fails(lambda table, _n: table == "fact_inventory_snapshot", boom),
    )
    rejected = (RejectedRecord("feed", 3, RejectionStage.PARSING, ("bad",), {}),)

    with pytest.raises(WarehouseWriteError) as info:
        _load(warehouse, [_item()], rejected)

    assert info.value.context == {"sqlstate": "53100"}
    assert _locations(warehouse) == []
    assert _count(warehouse, "SELECT count(*) FROM operational.rejected_records") == 0
    assert _count(warehouse, "SELECT count(*) FROM operational.inventory_run_results") == 0


def test_a_lost_connection_is_retried_and_data_is_written_once(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(
        loader_module,
        "upsert",
        _upsert_that_fails(lambda table, n: table == "dim_location" and n == 1, lost),
    )

    result = _load(warehouse, [_item(), _item(product_id="SUP-001:S1-00013")])

    assert result.rows_written == 2
    assert len(_locations(warehouse)) == 1


def test_a_connection_that_never_returns_raises_the_connection_error(
    warehouse: Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    lost = DatabaseConnectionError("connection lost")
    monkeypatch.setattr(loader_module, "upsert", _upsert_that_fails(lambda _t, _n: True, lost))

    with pytest.raises(DatabaseConnectionError):
        _load(warehouse, [_item()])

    assert _locations(warehouse) == []


def test_a_failure_is_recorded_with_its_stage(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    record_failure(warehouse, "run-1", SchemaValidationError("missing fields"))
    finish_run(warehouse, "run-1", RunStatus.FAILED)

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT status, failed_stage, error_message FROM operational.inventory_run_results"
        ).fetchone()
        run = conn.execute("SELECT status FROM operational.pipeline_runs").fetchone()
    assert row == ("failed", "validation", "missing fields")
    assert run == ("failed",)
