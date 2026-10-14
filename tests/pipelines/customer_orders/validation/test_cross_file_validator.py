import polars as pl
from src.pipelines.customer_orders.validation import (
    DefaultCustomerOrdersCrossFileValidator,
)


def test_rejects_order_with_unknown_customer() -> None:
    customers = pl.DataFrame({"customer_id": ["C001"], "name": ["Alice"]})
    orders = pl.DataFrame(
        {
            "order_id": ["O001"],
            "customer_id": ["C999"],
            "ordered_at": ["2026-09-01T10:00:00Z"],
            "status": ["PLACED"],
            "cancelled_at": [None],
        }
    )
    order_lines = pl.DataFrame(
        {
            "order_line_id": ["L001"],
            "order_id": ["O001"],
            "product_id": ["P001"],
            "quantity": ["2"],
            "unit_price_amount": ["10.00"],
            "unit_price_currency": ["USD"],
        }
    )

    result = DefaultCustomerOrdersCrossFileValidator().validate(
        customers, orders, order_lines
    )

    assert result.orders.valid.is_empty()
    assert result.orders.rejected.height == 1
    assert (
        result.orders.rejected["_cross_file_errors"][0]
        == "customer_id does not reference a valid customer"
    )
    assert result.order_lines.valid.is_empty()
    assert result.order_lines.rejected.height == 1


def test_rejects_order_without_order_lines() -> None:
    customers = pl.DataFrame({"customer_id": ["C001"], "name": ["Alice"]})
    orders = pl.DataFrame(
        {
            "order_id": ["O001"],
            "customer_id": ["C001"],
            "ordered_at": ["2026-09-01T10:00:00Z"],
            "status": ["PLACED"],
            "cancelled_at": [None],
        }
    )
    order_lines = pl.DataFrame(
        schema={
            "order_line_id": pl.String,
            "order_id": pl.String,
            "product_id": pl.String,
            "quantity": pl.String,
            "unit_price_amount": pl.String,
            "unit_price_currency": pl.String,
        }
    )

    result = DefaultCustomerOrdersCrossFileValidator().validate(
        customers, orders, order_lines
    )

    assert result.orders.valid.is_empty()
    assert result.orders.rejected.height == 1
    assert (
        result.orders.rejected["_cross_file_errors"][0]
        == "order must contain at least one valid order line"
    )


def test_accepts_consistent_customer_order_and_line() -> None:
    customers = pl.DataFrame({"customer_id": ["C001"], "name": ["Alice"]})
    orders = pl.DataFrame(
        {
            "order_id": ["O001"],
            "customer_id": ["C001"],
            "ordered_at": ["2026-09-01T10:00:00Z"],
            "status": ["PLACED"],
            "cancelled_at": [None],
        }
    )
    order_lines = pl.DataFrame(
        {
            "order_line_id": ["L001"],
            "order_id": ["O001"],
            "product_id": ["P001"],
            "quantity": ["2"],
            "unit_price_amount": ["10.00"],
            "unit_price_currency": ["USD"],
        }
    )

    result = DefaultCustomerOrdersCrossFileValidator().validate(
        customers, orders, order_lines
    )

    assert result.orders.valid.height == 1
    assert result.orders.rejected.is_empty()
    assert result.order_lines.valid.height == 1
    assert result.order_lines.rejected.is_empty()
