import polars as pl
from src.pipelines.customer_orders.validation.result import ValidationResult

_CROSS_FILE_ERRORS_COLUMN = "_cross_file_errors"
_VALIDATION_ERRORS_COLUMN = "_validation_errors"


class CustomerOrdersCrossFileValidationResult:
    def __init__(
        self,
        orders: ValidationResult,
        order_lines: ValidationResult,
    ) -> None:
        self.orders = orders
        self.order_lines = order_lines


class DefaultCustomerOrdersCrossFileValidator:
    def validate(
        self,
        customers: pl.DataFrame,
        orders: pl.DataFrame,
        order_lines: pl.DataFrame,
    ) -> CustomerOrdersCrossFileValidationResult:
        valid_customer_ids = customers.get_column("customer_id")
        valid_order_ids = orders.get_column("order_id")

        # Orders must reference an accepted customer.
        invalid_customer_orders = orders.filter(
            ~pl.col("customer_id").is_in(valid_customer_ids)
        )

        valid_customer_orders = orders.filter(
            pl.col("customer_id").is_in(valid_customer_ids)
        )

        rejected_orders = self._reject(
            invalid_customer_orders,
            "customer_id does not reference a valid customer",
        )

        # Order lines must reference an accepted order.
        valid_order_ids = valid_customer_orders.get_column("order_id")

        invalid_order_lines = order_lines.filter(
            ~pl.col("order_id").is_in(valid_order_ids)
        )

        valid_order_lines = order_lines.filter(
            pl.col("order_id").is_in(valid_order_ids)
        )

        rejected_order_lines = self._reject(
            invalid_order_lines,
            "order_id does not reference a valid order",
        )

        # Every accepted order must have at least one accepted line.
        orders_with_lines = valid_order_lines.get_column("order_id").unique()

        orders_without_lines = valid_customer_orders.filter(
            ~pl.col("order_id").is_in(orders_with_lines)
        )

        rejected_orders = self._combine(
            rejected_orders,
            self._reject(
                orders_without_lines,
                "order must contain at least one valid order line",
            ),
        )

        valid_orders = valid_customer_orders.filter(
            pl.col("order_id").is_in(orders_with_lines)
        )

        return CustomerOrdersCrossFileValidationResult(
            orders=ValidationResult(
                valid=valid_orders,
                rejected=rejected_orders,
            ),
            order_lines=ValidationResult(
                valid=valid_order_lines,
                rejected=rejected_order_lines,
            ),
        )

    @staticmethod
    def _reject(data: pl.DataFrame, reason: str) -> pl.DataFrame:
        if data.is_empty():
            return data.with_columns(
                pl.Series(_CROSS_FILE_ERRORS_COLUMN, [], dtype=pl.String)
            )

        return data.with_columns(pl.lit(reason).alias(_CROSS_FILE_ERRORS_COLUMN))

    @staticmethod
    def _combine(
        existing: pl.DataFrame,
        additional: pl.DataFrame,
    ) -> pl.DataFrame:
        if existing.is_empty():
            return additional
        if additional.is_empty():
            return existing

        return pl.concat(
            [existing, additional],
            how="diagonal_relaxed",
        )
