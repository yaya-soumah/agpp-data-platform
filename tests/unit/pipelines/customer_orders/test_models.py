from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agpp.pipelines.customer_orders.models import Customer, OrderLine, OrderStatus

VALUES = {
    "order_id": "O-1001",
    "line_number": "1",
    "customer_id": "cus-00042",
    "customer_name": "  Marie Dupont ",
    "customer_country": "lu",
    "ordered_at": "2026-11-09T10:00:00+01:00",
    "product_id": " sup-001:s1-00012 ",
    "quantity": "3",
    "unit_price": "12.5",
    "currency": "eur",
    "status": " Shipped ",
    "updated_at": "2026-11-09T12:00:00Z",
}


def test_text_values_are_converted_to_types() -> None:
    line = OrderLine.model_validate(VALUES)

    assert line.line_number == 1
    assert line.quantity == 3
    assert line.unit_price == Decimal("12.5")
    assert line.status is OrderStatus.SHIPPED


def test_values_are_normalized() -> None:
    line = OrderLine.model_validate(VALUES)

    assert line.customer_id == "CUS-00042"
    assert line.customer_name == "Marie Dupont"
    assert line.customer_country == "LU"
    assert line.product_id == "SUP-001:S1-00012"
    assert line.currency == "EUR"


def test_timestamps_are_converted_to_utc() -> None:
    line = OrderLine.model_validate(VALUES)

    assert line.ordered_at == datetime(2026, 11, 9, 9, 0, tzinfo=UTC)
    assert line.ordered_at.tzinfo is UTC


def test_the_line_amount_is_quantity_times_price() -> None:
    assert OrderLine.model_validate(VALUES).line_amount == Decimal("37.5")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order_id", ""),
        ("order_id", "x" * 31),
        ("line_number", "0"),
        ("customer_id", "CUS-1"),
        ("customer_name", "  "),
        ("customer_country", "LUX"),
        ("ordered_at", "2026-11-09T10:00:00"),
        ("ordered_at", "yesterday"),
        ("product_id", "A-1"),
        ("product_id", "SUP-1:A-1"),
        ("quantity", "0"),
        ("quantity", "10001"),
        ("unit_price", "0"),
        ("unit_price", "1.23456"),
        ("currency", "EURO"),
        ("status", "lost"),
        ("updated_at", "2026-11-09T12:00:00"),
    ],
)
def test_invalid_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as info:
        OrderLine.model_validate({**VALUES, field: value})

    assert field in str(info.value)


def test_missing_fields_are_rejected() -> None:
    data = {k: v for k, v in VALUES.items() if k != "status"}

    with pytest.raises(ValidationError, match="status"):
        OrderLine.model_validate(data)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="colour"):
        OrderLine.model_validate({**VALUES, "colour": "red"})


def test_a_customer_accepts_valid_data() -> None:
    customer = Customer(customer_id="CUS-00001", name="Marie Dupont", country="LU")

    assert customer.name == "Marie Dupont"


@pytest.mark.parametrize(
    ("field", "value"),
    [("customer_id", "CUS-1"), ("country", "lux"), ("name", "")],
)
def test_a_customer_rejects_invalid_data(field: str, value: str) -> None:
    data = {"customer_id": "CUS-00001", "name": "Marie", "country": "LU", field: value}

    with pytest.raises(ValidationError, match=field):
        Customer.model_validate(data)
