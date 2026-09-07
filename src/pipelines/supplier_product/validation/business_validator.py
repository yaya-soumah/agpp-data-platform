import polars as pl
from src.shared.currency import Currency

from .result import ValidationResult

_VALIDATION_ERRORS_COLUMN = "_validation_errors"

_VALID_PRICE_PATTERN = r"^(?:[0-9]*[1-9][0-9]*)(?:\.[0-9]+)?$|^0+\.[0-9]*[1-9][0-9]*$"

_SUPPORTED_CURRENCIES = [currency.value for currency in Currency]


class DefaultSupplierProductBusinessValidator:
    """Validates supplier-product business rules."""

    def validate(self, data: pl.DataFrame) -> ValidationResult:
        """
        Validate the supplier-product business rules on the given DataFrame.

        Args:
            data (pl.DataFrame): The DataFrame containing supplier-product data to validate.
        return
            ValidationResult: The result of the validation.
        """

        validation_errors = pl.concat_list(
            [
                pl.when(
                    pl.col("supplier_product_id").is_null()
                    | pl.col("supplier_product_id").str.strip_chars().eq("")
                )
                .then(pl.lit("supplier_product_id is required"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(
                    pl.col("supplier_id").is_null()
                    | pl.col("supplier_id").str.strip_chars().eq("")
                )
                .then(pl.lit("supplier_id is required"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(
                    pl.col("name").is_null() | pl.col("name").str.strip_chars().eq("")
                )
                .then(pl.lit("name is required"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(
                    pl.col("price").is_not_null()
                    & (
                        pl.col("price").str.strip_chars().eq("")
                        | ~pl.col("price")
                        .str.strip_chars()
                        .str.contains(_VALID_PRICE_PATTERN)
                    )
                )
                .then(pl.lit("price must be a positive decimal"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(pl.col("price").is_null() != pl.col("currency").is_null())
                .then(pl.lit("price and currency must be provided together"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(
                    pl.col("currency").is_not_null()
                    & ~pl.col("currency").is_in(_SUPPORTED_CURRENCIES)
                )
                .then(pl.lit("currency is not supported"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(
                    pl.col("minimum_order_quantity").is_not_null()
                    & (pl.col("minimum_order_quantity") <= 0)
                )
                .then(pl.lit("minimum_order_quantity must be greater than zero"))
                .otherwise(pl.lit(None, dtype=pl.String)),
                pl.when(
                    pl.col("lead_time_days").is_not_null()
                    & (pl.col("lead_time_days") < 0)
                )
                .then(pl.lit("lead_time_days must be greater than or equal to zero"))
                .otherwise(pl.lit(None, dtype=pl.String)),
            ]
        ).list.drop_nulls()

        evaluated = data.with_columns(
            validation_errors.alias(_VALIDATION_ERRORS_COLUMN)
        )

        rejected = evaluated.filter(pl.col(_VALIDATION_ERRORS_COLUMN).list.len() > 0)

        valid = evaluated.filter(
            pl.col(_VALIDATION_ERRORS_COLUMN).list.len() == 0
        ).drop(_VALIDATION_ERRORS_COLUMN)

        rejected = rejected.with_columns(
            pl.col(_VALIDATION_ERRORS_COLUMN).list.join("; ")
        )

        return ValidationResult(
            valid=valid,
            rejected=rejected,
        )
