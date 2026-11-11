from datetime import UTC, datetime
from decimal import Decimal

import pytest

from agpp.pipelines.customer_orders.models import OrderLine
from agpp.pipelines.customer_orders.transformation import to_rows, transform_orders
from agpp.pipelines.customer_orders.transformation.transformer import collapse_whitespace
from agpp.pipelines.customer_orders.validation import ValidationResult
from agpp.shared.exceptions import TransformationError

VALUES = {
    "order_id": "O-1001",
    "line_number": "1",
    "customer_id": "CUS-00042",
    "customer_name": "Marie Dupont",
    "customer_country": "LU",
    "ordered_at": "2026-11-09T23:30:00Z",
    "product_id": "SUP-001:S1-00012",
    "quantity": "3",
    "unit_price": "12.5",
    "currency": "EUR",
    "status": "shipped",
    "updated_at": "2026-11-09T23:45:00Z",
}


def _line(**overrides: str) -> OrderLine:
    return OrderLine.model_validate({**VALUES, **overrides})


def test_collapse_whitespace() -> None:
    assert collapse_whitespace("  Marie \t Dupont\n") == "Marie Dupont"


def test_a_line_is_mapped_to_a_fact_row() -> None:
    row = to_rows([_line()]).lines[0]

    assert (row.order_id, row.line_number) == ("O-1001", 1)
    assert row.customer_id == "CUS-00042"
    assert row.product_id == "SUP-001:S1-00012"
    assert row.currency == "EUR"
    assert row.status == "shipped"
    assert row.ordered_at == datetime(2026, 11, 9, 23, 30, tzinfo=UTC)
    assert row.source_updated_at == datetime(2026, 11, 9, 23, 45, tzinfo=UTC)


def test_the_line_amount_and_price_are_fixed_to_four_decimals() -> None:
    row = to_rows([_line()]).lines[0]

    assert row.line_amount == Decimal("37.5")
    assert str(row.line_amount) == "37.5000"
    assert str(row.unit_price) == "12.5000"


def test_the_date_key_uses_the_utc_date_of_the_order() -> None:
    row = to_rows([_line(ordered_at="2026-11-10T00:30:00+01:00")]).lines[0]

    assert row.date_key == 20261109


def test_customers_are_distinct_and_sorted() -> None:
    lines = [
        _line(order_id="O-1", customer_id="CUS-00002"),
        _line(order_id="O-2", customer_id="CUS-00001"),
        _line(order_id="O-3", customer_id="CUS-00002"),
    ]

    transformed = to_rows(lines)

    assert [c.customer_id for c in transformed.customers] == ["CUS-00001", "CUS-00002"]
    assert len(transformed.lines) == 3


def test_a_customer_takes_its_details_from_its_latest_line() -> None:
    lines = [
        _line(order_id="O-1", customer_name="Old   Name", updated_at="2026-11-09T10:00:00Z"),
        _line(order_id="O-2", customer_name="New Name", updated_at="2026-11-09T12:00:00Z"),
        _line(order_id="O-3", customer_name="Middle Name", updated_at="2026-11-09T11:00:00Z"),
    ]

    customer = to_rows(lines).customers[0]

    assert customer.customer_name == "New Name"
    assert customer.source_updated_at == datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def test_transformation_is_deterministic() -> None:
    lines = [_line(order_id="O-1"), _line(order_id="O-2")]

    assert to_rows(lines) == to_rows(lines)


def test_no_lines_give_no_rows() -> None:
    transformed = to_rows([])

    assert transformed.customers == ()
    assert transformed.lines == ()


def test_a_repeated_order_line_is_rejected() -> None:
    with pytest.raises(TransformationError, match="Duplicate order line"):
        to_rows([_line(), _line()])


def test_the_stage_transforms_the_valid_lines() -> None:
    result = ValidationResult("orders.csv", 2, (_line(order_id="O-1"), _line(order_id="O-2")), ())

    transformed = transform_orders(result, run_id="run-1")

    assert len(transformed.lines) == 2
