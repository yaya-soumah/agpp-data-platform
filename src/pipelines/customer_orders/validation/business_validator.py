import polars as pl
from src.pipelines.customer_orders.models import ORDER_STATUS_VALUES
from src.pipelines.customer_orders.validation.result import ValidationResult
from src.shared.currency import Currency

_ERRORS_COLUMN = "_validation_errors"
_SUPPORTED_CURRENCIES = [currency.value for currency in Currency]

_VALID_DECIMAL_PATTERN = r"^[0-9]+(?:\.[0-9]+)?$"


class DefaultCustomerOrdersBusinessValidator:
    """Validate customer-orders business rules."""

    def validate(
        self,
        data: pl.DataFrame,
        dataset_name: str,
    ) -> ValidationResult:
        if dataset_name == "orders":
            errors = self._validate_orders()
        elif dataset_name == "order_lines":
            errors = self._validate_order_lines()
        elif dataset_name == "customers":
            return ValidationResult(valid=data, rejected=data.head(0))
        else:
            raise ValueError(f"Unsupported dataset: {dataset_name}")

        evaluated = data.with_columns(
            pl.concat_list(errors).list.drop_nulls().alias(_ERRORS_COLUMN)
        )

        rejected = evaluated.filter(pl.col(_ERRORS_COLUMN).list.len() > 0).with_columns(
            pl.col(_ERRORS_COLUMN).list.join("; ")
        )
        valid = evaluated.filter(pl.col(_ERRORS_COLUMN).list.len() == 0).drop(
            _ERRORS_COLUMN
        )

        return ValidationResult(valid=valid, rejected=rejected)

    @staticmethod
    def _validate_orders() -> list[pl.Expr]:
        return [
            pl.when(~pl.col("status").is_in(ORDER_STATUS_VALUES))
            .then(pl.lit("status is not supported"))
            .otherwise(pl.lit(None, dtype=pl.String)),
            pl.when(
                pl.col("ordered_at")
                .str.to_datetime(strict=False, time_zone="UTC")
                .is_null()
            )
            .then(pl.lit("ordered_at must be a valid timestamp"))
            .otherwise(pl.lit(None, dtype=pl.String)),
            pl.when(
                (pl.col("status") == "PLACED")
                & pl.col("cancelled_at").is_not_null()
                & pl.col("cancelled_at").str.strip_chars().ne("")
            )
            .then(pl.lit("cancelled_at must be empty for PLACED orders"))
            .otherwise(pl.lit(None, dtype=pl.String)),
            pl.when(
                (pl.col("status") == "CANCELLED")
                & (
                    pl.col("cancelled_at").is_null()
                    | pl.col("cancelled_at").str.strip_chars().eq("").fill_null(True)
                    | pl.col("cancelled_at")
                    .str.to_datetime(strict=False, time_zone="UTC")
                    .is_null()
                )
            )
            .then(pl.lit("CANCELLED orders require a valid cancelled_at"))
            .otherwise(pl.lit(None, dtype=pl.String)),
        ]

    @staticmethod
    def _validate_order_lines() -> list[pl.Expr]:
        return [
            pl.when(
                ~pl.col("quantity").str.contains(_VALID_DECIMAL_PATTERN)
                | (
                    pl.col("quantity").cast(
                        pl.Decimal(precision=38, scale=6), strict=False
                    )
                    <= 0
                ).fill_null(True)
            )
            .then(pl.lit("quantity must be a positive decimal"))
            .otherwise(pl.lit(None, dtype=pl.String)),
            pl.when(
                ~pl.col("unit_price_amount").str.contains(_VALID_DECIMAL_PATTERN)
                | (
                    pl.col("unit_price_amount").cast(
                        pl.Decimal(precision=38, scale=6), strict=False
                    )
                    < 0
                ).fill_null(True)
            )
            .then(pl.lit("unit_price_amount must be a non-negative decimal"))
            .otherwise(pl.lit(None, dtype=pl.String)),
            pl.when(~pl.col("unit_price_currency").is_in(_SUPPORTED_CURRENCIES))
            .then(pl.lit("unit_price_currency is not supported"))
            .otherwise(pl.lit(None, dtype=pl.String)),
        ]
