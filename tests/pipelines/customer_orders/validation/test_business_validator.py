import polars as pl
from src.pipelines.customer_orders.validation import (
    DefaultCustomerOrdersBusinessValidator,
)


def test_rejects_unsupported_order_status() -> None:
    data = pl.DataFrame(
        {
            "order_id": ["O001"],
            "customer_id": ["C001"],
            "ordered_at": ["2026-10-01T10:00:00Z"],
            "status": ["SHIPPED"],
            "cancelled_at": [None],
        },
        schema_overrides={"cancelled_at": pl.String},
    )

    result = DefaultCustomerOrdersBusinessValidator().validate(data, "orders")

    assert result.valid.is_empty()
    assert "status is not supported" in result.rejected["_validation_errors"][0]


def test_rejects_non_positive_quantity() -> None:
    data = pl.DataFrame(
        {
            "order_line_id": ["L001"],
            "order_id": ["O001"],
            "product_id": ["P001"],
            "quantity": ["0"],
            "unit_price_amount": ["10.00"],
            "unit_price_currency": ["USD"],
        }
    )

    result = DefaultCustomerOrdersBusinessValidator().validate(data, "order_lines")

    assert result.valid.is_empty()
    assert (
        "quantity must be a positive decimal"
        in result.rejected["_validation_errors"][0]
    )
