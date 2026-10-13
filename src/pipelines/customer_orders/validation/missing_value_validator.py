import polars as pl

from .result import ValidationResult

_ERRORS_COLUMN = "_validation_errors"
_REQUIRED_FIELDS = {
    "customers": ("customer_id", "name"),
    "orders": ("order_id", "customer_id", "ordered_at", "status"),
    "order_lines": (
        "order_line_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price_amount",
        "unit_price_currency",
    ),
}


class DefaultCustomerOrdersMissingValueValidator:
    """Reject rows missing required customer-orders values."""

    def validate(
        self,
        data: pl.DataFrame,
        dataset_name: str,
    ) -> ValidationResult:
        required_fields = _REQUIRED_FIELDS[dataset_name]

        errors = pl.concat_list(
            [
                pl.when(
                    pl.col(column).is_null()
                    | (pl.col(column).str.strip_chars().eq("").fill_null(False))
                )
                .then(pl.lit(f"{column} is required"))
                .otherwise(pl.lit(None, dtype=pl.String))
                for column in required_fields
            ]
        ).list.drop_nulls()

        evaluated = data.with_columns(errors.alias(_ERRORS_COLUMN))
        rejected = evaluated.filter(pl.col(_ERRORS_COLUMN).list.len() > 0).with_columns(
            pl.col(_ERRORS_COLUMN).list.join("; ")
        )
        valid = evaluated.filter(pl.col(_ERRORS_COLUMN).list.len() == 0).drop(
            _ERRORS_COLUMN
        )

        return ValidationResult(valid=valid, rejected=rejected)
