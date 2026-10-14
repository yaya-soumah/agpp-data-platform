import polars as pl
from src.pipelines.customer_orders.validation.result import ValidationResult

_DUPLICATE_ERRORS_COLUMN = "_duplicate_errors"

_IDENTIFIER_COLUMNS = {
    "customers": "customer_id",
    "orders": "order_id",
    "order_lines": "order_line_id",
}


class DefaultCustomerOrdersDuplicateDetector:
    """Reject every row participating in a duplicate business identifier."""

    def detect(
        self,
        data: pl.DataFrame,
        dataset_name: str,
    ) -> ValidationResult:
        identifier = _IDENTIFIER_COLUMNS[dataset_name]

        duplicate_ids = (
            data.group_by(identifier).len().filter(pl.col("len") > 1).select(identifier)
        )

        rejected = data.join(
            duplicate_ids,
            on=identifier,
            how="semi",
        ).with_columns(
            pl.lit(f"{identifier} is duplicated").alias(_DUPLICATE_ERRORS_COLUMN)
        )

        valid = data.join(
            duplicate_ids,
            on=identifier,
            how="anti",
        )

        return ValidationResult(valid=valid, rejected=rejected)
