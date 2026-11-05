from pathlib import Path
from typing import LiteralString

import pytest
from psycopg.types.json import Jsonb

from agpp.shared.database import Pool, connection
from agpp.shared.database.migrations import apply_migrations
from agpp.shared.database.warehouse import upsert
from agpp.shared.exceptions import InfrastructureError

UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"

SUPPLIER_COLUMNS = ["supplier_id", "supplier_name", "country"]
SUPPLIER = ("SUP-001", "Alpine Components", "LU")


@pytest.fixture
def warehouse(scratch_pool: Pool, project_root: Path) -> Pool:
    apply_migrations(scratch_pool, project_root / "sql" / "migrations")
    return scratch_pool


def _load_supplier(pool: Pool, row: tuple[str, str, str] = SUPPLIER) -> int:
    """Upsert the supplier and return the number of rows written."""
    with connection(pool) as conn:
        result = upsert(
            conn,
            schema="warehouse",
            table="dim_supplier",
            columns=SUPPLIER_COLUMNS,
            conflict_columns=["supplier_id"],
            rows=[row],
        )
    return result.written


def _supplier_key(pool: Pool) -> int:
    with connection(pool) as conn:
        found = conn.execute(
            "SELECT supplier_key FROM warehouse.dim_supplier WHERE supplier_id = 'SUP-001'"
        ).fetchone()
    assert found is not None
    return int(found[0])


def _insert_product(
    pool: Pool,
    supplier_key: int,
    *,
    product_id: str = "SUP-001:A-1",
    supplier_sku: str = "A-1",
    unit_price: str = "10.00",
    currency: str = "EUR",
    min_order_quantity: int = 1,
    lead_time_days: int = 5,
) -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.dim_product (product_id, supplier_key, supplier_sku,"
            " product_name, category, unit_price, currency, min_order_quantity,"
            " lead_time_days, is_active, source_updated_at)"
            " VALUES (%s, %s, %s, 'Hex Bolt', 'Fasteners', %s, %s, %s, %s, true, now())",
            (
                product_id,
                supplier_key,
                supplier_sku,
                unit_price,
                currency,
                min_order_quantity,
                lead_time_days,
            ),
        )


def _sqlstate_of(pool: Pool, action: LiteralString) -> object:
    with pytest.raises(InfrastructureError) as info, connection(pool) as conn:
        conn.execute(action)
    return info.value.context["sqlstate"]


def test_unknown_members_exist_in_both_dimensions(warehouse: Pool) -> None:
    with connection(warehouse) as conn:
        supplier = conn.execute(
            "SELECT supplier_id FROM warehouse.dim_supplier WHERE supplier_key = -1"
        ).fetchone()
        product = conn.execute(
            "SELECT product_id, supplier_key FROM warehouse.dim_product WHERE product_key = -1"
        ).fetchone()

    assert supplier == ("UNKNOWN",)
    assert product == ("UNKNOWN", -1)


def test_supplier_keys_are_generated_and_loads_are_idempotent(warehouse: Pool) -> None:
    assert _load_supplier(warehouse) == 1
    key = _supplier_key(warehouse)

    assert _load_supplier(warehouse) == 0
    assert _supplier_key(warehouse) == key
    assert key > 0


def test_a_changed_supplier_name_is_overwritten_not_duplicated(warehouse: Pool) -> None:
    _load_supplier(warehouse)

    written = _load_supplier(warehouse, ("SUP-001", "Alpine Components SA", "LU"))

    with connection(warehouse) as conn:
        rows = conn.execute(
            "SELECT supplier_name FROM warehouse.dim_supplier WHERE supplier_id = 'SUP-001'"
        ).fetchall()
    assert written == 1
    assert rows == [("Alpine Components SA",)]


def test_a_supplier_country_must_be_two_capital_letters(warehouse: Pool) -> None:
    state = _sqlstate_of(
        warehouse,
        "INSERT INTO warehouse.dim_supplier (supplier_id, supplier_name, country)"
        " VALUES ('SUP-002', 'Bad', 'lux')",
    )

    assert state == CHECK_VIOLATION


def test_a_valid_product_is_accepted_with_four_decimal_places(warehouse: Pool) -> None:
    _load_supplier(warehouse)

    _insert_product(warehouse, _supplier_key(warehouse))

    with connection(warehouse) as conn:
        price = conn.execute(
            "SELECT unit_price FROM warehouse.dim_product WHERE product_id = 'SUP-001:A-1'"
        ).fetchone()
    assert price is not None
    assert str(price[0]) == "10.0000"


def test_a_product_needs_an_existing_supplier(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_product(warehouse, 99999)

    assert info.value.context["sqlstate"] == FOREIGN_KEY_VIOLATION


def test_the_product_business_key_is_unique(warehouse: Pool) -> None:
    _load_supplier(warehouse)
    key = _supplier_key(warehouse)
    _insert_product(warehouse, key)

    with pytest.raises(InfrastructureError) as info:
        _insert_product(warehouse, key)

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


def test_a_sku_is_unique_per_supplier(warehouse: Pool) -> None:
    _load_supplier(warehouse)
    key = _supplier_key(warehouse)
    _insert_product(warehouse, key)

    with pytest.raises(InfrastructureError) as info:
        _insert_product(warehouse, key, product_id="SUP-001:OTHER")

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


@pytest.mark.parametrize(
    "invalid",
    [
        {"unit_price": "0"},
        {"unit_price": "-1"},
        {"currency": "eur"},
        {"min_order_quantity": 0},
        {"lead_time_days": 366},
    ],
)
def test_product_values_are_checked_by_the_database(
    warehouse: Pool, invalid: dict[str, object]
) -> None:
    _load_supplier(warehouse)
    key = _supplier_key(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _insert_product(warehouse, key, **invalid)  # type: ignore[arg-type]

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def _insert_rejected(pool: Pool, line: int = 7, stage: str = "parsing") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.rejected_records"
            " (run_id, pipeline, supplier_id, line_number, stage, reasons, raw_values)"
            " VALUES ('run-1', 'supplier_product', 'SUP-001', %s, %s, %s, %s)",
            (line, stage, Jsonb(["unit_price: bad"]), Jsonb({"unit_price": "x"})),
        )


def test_rejected_records_keep_reasons_and_raw_values_as_json(warehouse: Pool) -> None:
    _insert_rejected(warehouse)

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT reasons, raw_values, stage FROM operational.rejected_records"
        ).fetchone()

    assert row == (["unit_price: bad"], {"unit_price": "x"}, "parsing")


def test_a_line_can_be_rejected_only_once_per_run(warehouse: Pool) -> None:
    _insert_rejected(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _insert_rejected(warehouse)

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


def test_the_rejection_stage_is_restricted(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_rejected(warehouse, stage="other")

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_applying_all_migrations_again_changes_nothing(warehouse: Pool, project_root: Path) -> None:
    assert apply_migrations(warehouse, project_root / "sql" / "migrations") == []
