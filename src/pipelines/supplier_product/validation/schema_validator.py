import polars as pl
from src.shared.exceptions import ValidationError

from .schema import SUPPLIER_PRODUCT_SCHEMA


class DefaultSupplierProductSchemaValidator:
    """Validate supplier-product source data against its canonical schema."""

    def validate(self, data: pl.DataFrame) -> pl.DataFrame:

        actual_schema = data.schema

        expected_columns = set(SUPPLIER_PRODUCT_SCHEMA)
        actual_columns = set(actual_schema)

        missing_columns = sorted(expected_columns - actual_columns)
        unexpected_columns = sorted(actual_columns - expected_columns)

        type_mismatches = {
            column: {
                "expected": SUPPLIER_PRODUCT_SCHEMA[column],
                "actual": actual_schema[column],
            }
            for column in expected_columns & actual_columns
            if actual_schema[column] != SUPPLIER_PRODUCT_SCHEMA[column]
        }

        if missing_columns or unexpected_columns or type_mismatches:
            raise ValidationError(
                "Supplier-product source schema validation failed",
                error_code="VALIDATION_SUPPLIER_PRODUCT_SCHEMA_INVALID",
                context={
                    "missing_columns": missing_columns,
                    "unexpected_columns": unexpected_columns,
                    "type_mismatches": type_mismatches,
                },
                retryable=False,
            )
        return data
