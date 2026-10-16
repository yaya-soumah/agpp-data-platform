from dataclasses import dataclass
from logging import Logger

import polars as pl
from src.pipelines.customer_orders.extractors.base import CustomerOrdersBatch
from src.pipelines.customer_orders.models import (
    CUSTOMER_SCHEMA,
    ORDER_LINE_SCHEMA,
    ORDER_SCHEMA,
)
from src.pipelines.customer_orders.validation.business_validator import (
    DefaultCustomerOrdersBusinessValidator,
)
from src.pipelines.customer_orders.validation.cross_file_validator import (
    DefaultCustomerOrdersCrossFileValidator,
)
from src.pipelines.customer_orders.validation.duplicate_detector import (
    DefaultCustomerOrdersDuplicateDetector,
)
from src.pipelines.customer_orders.validation.missing_value_validator import (
    DefaultCustomerOrdersMissingValueValidator,
)
from src.pipelines.customer_orders.validation.result import ValidationResult
from src.pipelines.customer_orders.validation.schema_validator import (
    DefaultCustomerOrdersSchemaValidator,
)

_REJECTION_REASON_COLUMN = "_validation_errors"
_REASON_COLUMNS = (
    "_validation_errors",
    "_duplicate_errors",
    "_cross_file_errors",
)


@dataclass(frozen=True)
class CustomerOrdersValidationResult:
    customers: ValidationResult
    orders: ValidationResult
    order_lines: ValidationResult


class CustomerOrdersValidationService:
    def __init__(
        self,
        logger: Logger,
        schema_validator: DefaultCustomerOrdersSchemaValidator,
        missing_value_validator: DefaultCustomerOrdersMissingValueValidator,
        duplicate_detector: DefaultCustomerOrdersDuplicateDetector,
        business_validator: DefaultCustomerOrdersBusinessValidator,
        cross_file_validator: DefaultCustomerOrdersCrossFileValidator,
    ) -> None:
        self._logger = logger
        self._schema_validator = schema_validator
        self._missing_value_validator = missing_value_validator
        self._duplicate_detector = duplicate_detector
        self._business_validator = business_validator
        self._cross_file_validator = cross_file_validator

    def validate(
        self,
        batch: CustomerOrdersBatch,
    ) -> CustomerOrdersValidationResult:
        self._logger.info("Starting customer-orders validation.")

        # Structural errors invalidate the batch rather than individual rows.
        self._schema_validator.validate(batch.customers, CUSTOMER_SCHEMA, "customers")
        self._schema_validator.validate(batch.orders, ORDER_SCHEMA, "orders")
        self._schema_validator.validate(
            batch.order_lines, ORDER_LINE_SCHEMA, "order_lines"
        )

        customers, rejected_customers = self._validate_dataset(
            batch.customers, "customers"
        )
        orders, rejected_orders = self._validate_dataset(batch.orders, "orders")
        order_lines, rejected_order_lines = self._validate_dataset(
            batch.order_lines, "order_lines"
        )

        # Cross-file checks operate only on records accepted by all
        # preceding per-dataset validators.
        cross_file_result = self._cross_file_validator.validate(
            customers=customers,
            orders=orders,
            order_lines=order_lines,
        )

        rejected_orders.append(cross_file_result.orders.rejected)
        rejected_order_lines.append(cross_file_result.order_lines.rejected)

        result = CustomerOrdersValidationResult(
            customers=ValidationResult(
                valid=customers,
                rejected=self._combine_rejections(rejected_customers),
            ),
            orders=ValidationResult(
                valid=cross_file_result.orders.valid,
                rejected=self._combine_rejections(rejected_orders),
            ),
            order_lines=ValidationResult(
                valid=cross_file_result.order_lines.valid,
                rejected=self._combine_rejections(rejected_order_lines),
            ),
        )

        self._logger.info(
            "Customer-orders validation completed. "
            "Customers: %d valid, %d rejected; "
            "orders: %d valid, %d rejected; "
            "order lines: %d valid, %d rejected.",
            result.customers.valid.height,
            result.customers.rejected.height,
            result.orders.valid.height,
            result.orders.rejected.height,
            result.order_lines.valid.height,
            result.order_lines.rejected.height,
        )

        return result

    def _validate_dataset(
        self,
        data: pl.DataFrame,
        dataset_name: str,
    ) -> tuple[pl.DataFrame, list[pl.DataFrame]]:
        rejected: list[pl.DataFrame] = []

        missing_result = self._missing_value_validator.validate(data, dataset_name)
        rejected.append(self._normalize_rejections(missing_result.rejected))

        duplicate_result = self._duplicate_detector.detect(
            missing_result.valid, dataset_name
        )
        rejected.append(self._normalize_rejections(duplicate_result.rejected))

        business_result = self._business_validator.validate(
            duplicate_result.valid, dataset_name
        )
        rejected.append(self._normalize_rejections(business_result.rejected))

        return business_result.valid, rejected

    @staticmethod
    def _normalize_rejections(data: pl.DataFrame) -> pl.DataFrame:
        reason_column = next(
            (column for column in _REASON_COLUMNS if column in data.columns),
            None,
        )

        if reason_column is None:
            return data.with_columns(
                pl.lit(None, dtype=pl.String).alias(_REJECTION_REASON_COLUMN)
            )

        normalized = data.with_columns(
            pl.col(reason_column).cast(pl.String).alias(_REJECTION_REASON_COLUMN)
        )

        columns_to_drop = [
            column
            for column in _REASON_COLUMNS
            if column != _REJECTION_REASON_COLUMN and column in normalized.columns
        ]

        if columns_to_drop:
            normalized = normalized.drop(columns_to_drop)

        return normalized

    @classmethod
    def _combine_rejections(
        cls,
        rejected_frames: list[pl.DataFrame],
    ) -> pl.DataFrame:
        normalized_frames = [
            cls._normalize_rejections(frame) for frame in rejected_frames
        ]

        if not normalized_frames:
            raise ValueError("At least one rejection DataFrame is required.")

        return pl.concat(normalized_frames, how="diagonal_relaxed")
