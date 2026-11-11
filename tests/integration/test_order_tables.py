import pytest

from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import InfrastructureError

UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"


def _insert_customer(pool: Pool, customer_id: str = "CUS-00001", country: str = "LU") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.dim_customer"
            " (customer_id, customer_name, country, source_updated_at)"
            " VALUES (%s, 'Marie Dupont', %s, now())",
            (customer_id, country),
        )


def _insert_line(
    pool: Pool,
    *,
    order_id: str = "O-1",
    line_number: int = 1,
    customer_key: int = -1,
    product_key: int = -1,
    date_key: int = 20261109,
    quantity: int = 1,
    unit_price: str = "10.00",
    line_amount: str = "10.00",
    currency: str = "EUR",
    status: str = "placed",
) -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO warehouse.fact_order_line (order_id, line_number, customer_key,"
            " product_key, date_key, quantity, unit_price, line_amount, currency, status,"
            " ordered_at, source_updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())",
            (
                order_id,
                line_number,
                customer_key,
                product_key,
                date_key,
                quantity,
                unit_price,
                line_amount,
                currency,
                status,
            ),
        )


def test_the_unknown_customer_exists(warehouse: Pool) -> None:
    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT customer_id FROM warehouse.dim_customer WHERE customer_key = -1"
        ).fetchone()

    assert row == ("UNKNOWN",)


def test_the_customer_business_key_is_unique(warehouse: Pool) -> None:
    _insert_customer(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _insert_customer(warehouse)

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


def test_a_customer_country_must_be_two_capital_letters(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_customer(warehouse, country="lux")

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_a_line_may_point_at_the_unknown_customer_and_product(warehouse: Pool) -> None:
    _insert_line(warehouse, customer_key=-1, product_key=-1)

    with connection(warehouse) as conn:
        count = conn.execute("SELECT count(*) FROM warehouse.fact_order_line").fetchone()
    assert count == (1,)


@pytest.mark.parametrize(
    "dangling",
    [{"customer_key": 99999}, {"product_key": 99999}, {"date_key": 20500101}],
)
def test_lines_must_point_at_existing_dimension_rows(
    warehouse: Pool, dangling: dict[str, int]
) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_line(warehouse, **dangling)  # type: ignore[arg-type]

    assert info.value.context["sqlstate"] == FOREIGN_KEY_VIOLATION


def test_the_order_line_business_key_is_unique(warehouse: Pool) -> None:
    _insert_line(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _insert_line(warehouse)

    assert info.value.context["sqlstate"] == UNIQUE_VIOLATION


@pytest.mark.parametrize(
    "invalid",
    [
        {"quantity": 0},
        {"quantity": 10001},
        {"unit_price": "0"},
        {"line_amount": "0"},
        {"currency": "eur"},
        {"status": "lost"},
        {"line_number": 0},
    ],
)
def test_line_values_are_checked_by_the_database(
    warehouse: Pool, invalid: dict[str, object]
) -> None:
    with pytest.raises(InfrastructureError) as info:
        _insert_line(warehouse, **invalid)  # type: ignore[arg-type]

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def _start_run(pool: Pool) -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.pipeline_runs (run_id, pipeline, status)"
            " VALUES ('run-1', 'customer_orders', 'running')"
        )


def _result(pool: Pool, status: str, failed_stage: str | None, run_id: str = "run-1") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.order_run_results (run_id, status, failed_stage)"
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
