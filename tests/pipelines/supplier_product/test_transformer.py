from decimal import Decimal

import polars as pl
from src.pipelines.supplier_product import DefaultSupplierProductTransformer


def test_transform_converts_price_to_decimal_and_renames_curreny() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001"],
            "supplier_id": ["SUP-001"],
            "supplier_sku": ["ABC-500"],
            "name": ["Stainless Steel Bottle"],
            "description": ["Vacuum insulated bottle"],
            "price": ["8.50"],
            "currency": ["USD"],
            "minimum_order_quantity": [100],
            "lead_time_days": [7],
        }
    )

    result = DefaultSupplierProductTransformer().transform(data)

    assert result["price_amount"].dtype == pl.Decimal(38, 6)
    assert result["price_currency"].to_list() == ["USD"]
    assert result["price_amount"].to_list() == [8.5]
    assert "price" not in result.columns
    assert "currency" not in result.columns


def test_transform_converts_minimum_order_quantity_to_decimal() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001"],
            "supplier_id": ["SUP-001"],
            "supplier_sku": ["ABC-500"],
            "name": ["Bottle"],
            "price": ["8.50"],
            "currency": ["USD"],
            "minimum_order_quantity": [100],
            "lead_time_days": [7],
        }
    )

    result = DefaultSupplierProductTransformer().transform(data)

    assert result["minimum_order_quantity"].dtype == pl.Decimal(38, 6)
    assert result["minimum_order_quantity"].to_list() == [100]


def test_transform_preserves_decimal_precision_up_to_canonical_scale() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-002"],
            "supplier_id": ["SUP-001", "SUP-001"],
            "name": ["Product A", "Product B"],
            "price": ["8.50", "123.456789"],
            "currency": ["USD", "EUR"],
            "minimum_order_quantity": [100, 200],
            "lead_time_days": [7, 10],
        }
    )

    result = DefaultSupplierProductTransformer().transform(data)

    assert result["price_amount"].to_list() == [Decimal("8.5"), Decimal("123.456789")]


def test_transform_preserves_nulls() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001"],
            "supplier_id": ["SUP-001"],
            "name": ["Product"],
            "price": [None],
            "currency": [None],
            "minimum_order_quantity": [None],
            "lead_time_days": [7],
        },
        schema={
            "supplier_product_id": pl.String,
            "supplier_id": pl.String,
            "name": pl.String,
            "price": pl.String,
            "currency": pl.String,
            "minimum_order_quantity": pl.Int64,
            "lead_time_days": pl.Int64,
        },
    )

    result = DefaultSupplierProductTransformer().transform(data)

    assert result["price_amount"].is_null().all()
    assert result["price_currency"].is_null().all()
    assert result["minimum_order_quantity"].is_null().all()


def test_transform_preserves_non_transformed_columns() -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-001"],
            "supplier_id": ["SUP-001"],
            "supplier_sku": ["ABC-500"],
            "name": ["Product"],
            "description": ["Description"],
            "price": ["8.50"],
            "currency": ["USD"],
            "minimum_order_quantity": [100],
            "lead_time_days": [7],
        }
    )

    result = DefaultSupplierProductTransformer().transform(data)

    assert result["supplier_product_id"].to_list() == ["SP-001"]
    assert result["supplier_id"].to_list() == ["SUP-001"]
    assert result["supplier_sku"].to_list() == ["ABC-500"]
    assert result["name"].to_list() == ["Product"]
    assert result["description"].to_list() == ["Description"]
    assert result["lead_time_days"].to_list() == [7]
