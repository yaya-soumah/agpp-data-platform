import polars as pl
from src.shared.exceptions import ValidationError


class DefaultCustomerOrdersSchemaValidator:
    """Validate the structure of each customer-orders dataset."""

    def validate(
        self,
        data: pl.DataFrame,
        expected_schema: dict[str, type[pl.String]],
        dataset_name: str,
    ) -> pl.DataFrame:
        missing_columns = [
            column for column in expected_schema if column not in data.columns
        ]
        unexpected_columns = [
            column for column in data.columns if column not in expected_schema
        ]
        type_mismatches = {
            column: {
                "expected": str(expected_schema[column]),
                "actual": str(data.schema[column]),
            }
            for column in expected_schema.keys() & data.schema.keys()
            if data.schema[column] != expected_schema[column]
        }

        if missing_columns or unexpected_columns or type_mismatches:
            raise ValidationError(
                f"{dataset_name} schema validation failed",
                error_code="VALIDATION_CUSTOMER_ORDERS_SCHEMA_INVALID",
                context={
                    "dataset": dataset_name,
                    "missing_columns": missing_columns,
                    "unexpected_columns": unexpected_columns,
                    "type_mismatches": type_mismatches,
                },
                retryable=False,
            )

        return data
