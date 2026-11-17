import pytest

from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import InfrastructureError

UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"


def _insert_location(pool: Pool, code: str = "LU-01", country: str = "LU") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.dim_location"
            " (location_code, location_name, country, source_updated_at)"
            " VALUES (%s, 'Luxembourg Warehouse', %s, now())",
            (code, country),
        )


def _insert_snapshot(
    pool: Pool,
    *,
    date_key: int = 20261113,
    location_key: int = -1,
    product_id: str = "SUP-001:S1-00001",
    product_key: int = -1,
    on_hand: int = 100,
    reserved: int = 20,
    available: int = 80,
    reorder_point: int = 50,
    below: bool = False,
) -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.fact_inventory_snapshot (date_key, location_key, product_id,"
            " product_key, on_hand, reserved, available, reorder_point, below_reorder_point,"
            " snapshot_at, source_updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())",
            (
                date_key,
                location_key,
                product_id,
                product_key,
                on_hand,
                reserved,
                available,
                reorder_point,
                below,
            ),
        )


def _count(pool: Pool) -> int:
    with connection(pool) as conn:
        row = conn.execute("SELECT count(*) FROM warehouse.fact_inventory_snapshot").fetchone()
    assert row is not None
    return int(row[0])


def test_the_unknown_location_exists(warehouse: Pool) -> None:
    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT location_code FROM warehouse.dim_location WHERE location_key = -1"
        ).fetchone()

    assert row == ("UNKNOWN",)


def test_the_location_business_key_is_unique(warehouse: Pool) -> None:
    _insert_location(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _insert_location(warehouse)

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


@pytest.mark.parametrize("values", [{"code": "LUX-1"}, {"code": "lu-01"}, {"country": "lux"}])
def test_location_values_are_checked_by_the_database(
    warehouse: Pool, values: dict[str, str]
) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_location(warehouse, **values)

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_a_snapshot_may_point_at_the_unknown_location_and_product(warehouse: Pool) -> None:
    _insert_snapshot(warehouse)

    assert _count(warehouse) == 1


@pytest.mark.parametrize(
    "dangling",
    [{"location_key": 99999}, {"product_key": 99999}, {"date_key": 20500101}],
)
def test_snapshots_must_point_at_existing_dimension_rows(
    warehouse: Pool, dangling: dict[str, int]
) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_snapshot(warehouse, **dangling)  # type: ignore[arg-type]

    assert info.value.context["sqlstate"] == FOREIGN_KEY_VIOLATION


def test_the_snapshot_business_key_is_unique_per_day(warehouse: Pool) -> None:
    _insert_snapshot(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _insert_snapshot(warehouse)

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


def test_the_next_day_adds_a_row_and_unknown_products_stay_distinct(warehouse: Pool) -> None:
    _insert_snapshot(warehouse, date_key=20261113)
    _insert_snapshot(warehouse, date_key=20261114)
    _insert_snapshot(warehouse, date_key=20261113, product_id="SUP-001:S1-00002")

    assert _count(warehouse) == 3


@pytest.mark.parametrize(
    "invalid",
    [
        {"on_hand": -1, "reserved": 0, "available": -1},
        {"available": 70},
        {"on_hand": 10, "reserved": 20, "available": -10},
        {"below": True},
        {"reorder_point": -1},
        {"product_id": "A-1"},
    ],
)
def test_stock_values_are_checked_by_the_database(
    warehouse: Pool, invalid: dict[str, object]
) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_snapshot(warehouse, **invalid)  # type: ignore[arg-type]

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def _start_run(pool: Pool) -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.pipeline_runs (run_id, pipeline, status)"
            " VALUES ('run-1', 'inventory', 'running')"
        )


def _result(pool: Pool, status: str, failed_stage: str | None, run_id: str = "run-1") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.inventory_run_results (run_id, status, failed_stage)"
            " VALUES (%s, %s, %s)",
            (run_id, status, failed_stage),
        )


def test_a_run_result_needs_an_existing_run(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        _result(warehouse, "loaded", None)

    assert info.value.context["sqlstate"] == FOREIGN_KEY_VIOLATION


def test_run_results_keep_status_and_stage_consistent(warehouse: Pool) -> None:
    _start_run(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _result(warehouse, "loaded", "loading")

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_a_run_has_one_result(warehouse: Pool) -> None:
    _start_run(warehouse)
    _result(warehouse, "failed", "extraction")

    with pytest.raises(InfrastructureError) as info:
        _result(warehouse, "failed", "validation")

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION
