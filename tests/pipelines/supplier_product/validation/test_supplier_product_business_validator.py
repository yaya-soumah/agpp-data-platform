import polars as pl
import pytest
from src.pipelines.supplier_product.validation import (
    DefaultSupplierProductBusinessValidator,
)


@pytest.fixture
def validator() -> DefaultSupplierProductBusinessValidator:
    return DefaultSupplierProductBusinessValidator()


@pytest.fixture
def valid_data() -> pl.DataFrame:
    return pl.DataFrame(
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


def test_valid_data_is_accepted(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    result = validator.validate(valid_data)

    assert result.valid.equals(valid_data)
    assert result.rejected.height == 0


def test_valid_data_returns_same_schema(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    result = validator.validate(valid_data)

    assert result.valid.columns == valid_data.columns
    assert "_validation_errors" not in result.valid.columns


@pytest.mark.parametrize(
    "column",
    ["supplier_product_id", "supplier_id", "name"],
)
def test_required_fields_reject_null_values(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
    column: str,
) -> None:
    data = valid_data.with_columns(pl.lit(None).cast(pl.String).alias(column))

    result = validator.validate(data)

    assert result.valid.height == 0
    assert result.rejected.height == 1
    assert "is required" in result.rejected["_validation_errors"][0]


@pytest.mark.parametrize(
    "column",
    ["supplier_product_id", "supplier_id", "name"],
)
def test_required_fields_reject_blank_values(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
    column: str,
) -> None:
    data = valid_data.with_columns(pl.lit("   ").alias(column))

    result = validator.validate(data)

    assert result.valid.height == 0
    assert result.rejected.height == 1


@pytest.mark.parametrize(
    "price",
    ["", "   ", "abc", "-1.50", "0", "0.0", "0.00", "1,000.00"],
)
def test_invalid_prices_are_rejected(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
    price: str,
) -> None:
    data = valid_data.with_columns(pl.lit(price).alias("price"))

    result = validator.validate(data)

    assert result.valid.height == 0
    assert (
        "price must be a positive decimal" in result.rejected["_validation_errors"][0]
    )


@pytest.mark.parametrize(
    "price",
    ["1", "1.5", "8.50", "123456.789", "0.01"],
)
def test_valid_prices_are_accepted(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
    price: str,
) -> None:
    data = valid_data.with_columns(pl.lit(price).alias("price"))

    result = validator.validate(data)

    assert result.valid.height == 1
    assert result.rejected.height == 0


def test_missing_price_and_currency_are_allowed(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(
        pl.lit(None).cast(pl.String).alias("price"),
        pl.lit(None).cast(pl.String).alias("currency"),
    )

    result = validator.validate(data)

    assert result.valid.height == 1
    assert result.rejected.height == 0


def test_price_without_currency_is_rejected(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(pl.lit(None).cast(pl.String).alias("currency"))

    result = validator.validate(data)

    assert result.valid.height == 0
    assert (
        "price and currency must be provided together"
        in result.rejected["_validation_errors"][0]
    )


def test_currency_without_price_is_rejected(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(pl.lit(None).cast(pl.String).alias("price"))

    result = validator.validate(data)

    assert result.valid.height == 0
    assert (
        "price and currency must be provided together"
        in result.rejected["_validation_errors"][0]
    )


@pytest.mark.parametrize("currency", ["EUR", "USD", "CNY", "GBP"])
def test_supported_currencies_are_accepted(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
    currency: str,
) -> None:
    data = valid_data.with_columns(pl.lit(currency).alias("currency"))

    result = validator.validate(data)

    assert result.valid.height == 1


def test_unsupported_currency_is_rejected(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(pl.lit("JPY").alias("currency"))

    result = validator.validate(data)

    assert result.valid.height == 0
    assert "currency is not supported" in result.rejected["_validation_errors"][0]


def test_zero_moq_is_rejected(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(
        pl.lit(0).cast(pl.Int64).alias("minimum_order_quantity")
    )

    result = validator.validate(data)

    assert result.valid.height == 0


def test_negative_lead_time_is_rejected(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(pl.lit(-1).cast(pl.Int64).alias("lead_time_days"))

    result = validator.validate(data)

    assert result.valid.height == 0


def test_multiple_business_violations_are_reported(
    validator: DefaultSupplierProductBusinessValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(
        pl.lit("-5.00").alias("price"),
        pl.lit("JPY").alias("currency"),
        pl.lit(0).cast(pl.Int64).alias("minimum_order_quantity"),
    )

    result = validator.validate(data)

    assert result.valid.height == 0
    assert result.rejected.height == 1

    errors = result.rejected["_validation_errors"][0]

    assert "price must be a positive decimal" in errors
    assert "currency is not supported" in errors
    assert "minimum_order_quantity must be greater than zero" in errors
