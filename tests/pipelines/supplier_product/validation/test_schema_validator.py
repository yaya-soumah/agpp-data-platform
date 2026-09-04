import polars as pl
import pytest
from src.pipelines.supplier_product.validation import (
    SUPPLIER_PRODUCT_SCHEMA,
    DefaultSupplierProductSchemaValidator,
)
from src.shared.exceptions import ValidationError


@pytest.fixture
def validator() -> DefaultSupplierProductSchemaValidator:
    return DefaultSupplierProductSchemaValidator()


@pytest.fixture
def valid_data() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "supplier_product_id": ["SP-001"],
            "supplier_id": ["SUP-001"],
            "supplier_sku": ["ABC-500"],
            "name": ["Stainless Steel Bottle 500ml"],
            "description": ["Vacuum insulated stainless steel bottle"],
            "price": ["8.50"],
            "currency": ["USD"],
            "minimum_order_quantity": [100],
            "lead_time_days": [7],
        }
    )


def test_valid_schema_passes(
    validator: DefaultSupplierProductSchemaValidator,
    valid_data: pl.DataFrame,
) -> None:
    result = validator.validate(valid_data)

    assert result.equals(valid_data)


def test_valid_schema_returns_same_dataframe(
    validator: DefaultSupplierProductSchemaValidator,
    valid_data: pl.DataFrame,
) -> None:
    result = validator.validate(valid_data)

    assert result is valid_data


def test_missing_column_fails(
    validator: DefaultSupplierProductSchemaValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.drop("currency")

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(data)

    assert exc_info.value.error_code == "VALIDATION_SUPPLIER_PRODUCT_SCHEMA_INVALID"
    assert "missing_columns" in exc_info.value.context
    assert "currency" in exc_info.value.context["missing_columns"]


def test_unexpected_column_fails(
    validator: DefaultSupplierProductSchemaValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(pl.lit("extra").alias("unexpected_column"))

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(data)

    assert exc_info.value.error_code == "VALIDATION_SUPPLIER_PRODUCT_SCHEMA_INVALID"
    assert "unexpected_columns" in exc_info.value.context
    assert "unexpected_column" in exc_info.value.context["unexpected_columns"]


def test_wrong_dtype_fails(
    validator: DefaultSupplierProductSchemaValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.with_columns(pl.col("minimum_order_quantity").cast(pl.String))

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(data)

    assert exc_info.value.error_code == "VALIDATION_SUPPLIER_PRODUCT_SCHEMA_INVALID"
    assert "type_mismatches" in exc_info.value.context
    assert (
        exc_info.value.context["type_mismatches"]["minimum_order_quantity"]["expected"]
        == pl.Int64
    )


def test_nullable_values_are_allowed(
    validator: DefaultSupplierProductSchemaValidator,
) -> None:
    data = pl.DataFrame(
        {
            "supplier_product_id": ["SP-004"],
            "supplier_id": ["SUP-003"],
            "supplier_sku": [None],
            "name": ["Industrial Cable Ties"],
            "description": [None],
            "price": [None],
            "currency": [None],
            "minimum_order_quantity": [500],
            "lead_time_days": [5],
        },
        schema=SUPPLIER_PRODUCT_SCHEMA,
    )

    result = validator.validate(data)

    assert result.equals(data)


def test_multiple_schema_violations_are_reported(
    validator: DefaultSupplierProductSchemaValidator,
    valid_data: pl.DataFrame,
) -> None:
    data = valid_data.drop("currency").with_columns(
        pl.col("price").cast(pl.Float64),
        pl.lit("extra").alias("unexpected"),
    )

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(data)

    context = exc_info.value.context

    assert context["missing_columns"] == ["currency"]
    assert context["unexpected_columns"] == ["unexpected"]
    assert "price" in context["type_mismatches"]
