from logging import Logger
from pathlib import Path

import polars as pl
import csv

from src.shared.configuration.models import AppConfig
from src.shared.exceptions import DataExtractionError

from .base import CustomerOrdersBatch
from ..models.schema import (
    CUSTOMER_SCHEMA,
    ORDER_LINE_SCHEMA,
    ORDER_SCHEMA,
)

class CustomerOrderCSVExtractor:
    """Extract the three datasets of a customer-orders batch from CSV files."""

    _FILES = (
        ("customers.csv", CUSTOMER_SCHEMA),
        ("orders.csv", ORDER_SCHEMA),
        ("order_lines.csv", ORDER_LINE_SCHEMA),
    )

    def __init__(
        self,
        app_config: AppConfig,
        logger: Logger,
    ) -> None:
        self._app_config = app_config
        self._logger = logger

    def _read_header(self, path: Path) -> list[str]:
        with path.open("r", encoding="utf-8", newline="") as fh:
            return next(csv.reader(fh), [])

    def extract(self) -> CustomerOrdersBatch:
        """Extract all three datasets or raise an extraction error."""

        source_directory = Path(self._app_config.paths.raw_data)

        self._logger.info(
            "Starting customer-orders CSV extraction from '%s'.",
            source_directory
        )

        dataframes: dict[str, pl.DataFrame] = {}

        for filename, schema in self._FILES:
            source_path = source_directory / filename

            try:
                header = self._read_header(source_path)
            except OSError as exc:
                self._logger.error(
                    "Customer-orders CSV extractor failed for '%s': %s",
                    source_path, exc,
                )
                raise DataExtractionError(
                    f"Failed to extract customer-orders file '{filename}'",
                    error_code="EXTRACT_CUSTOMER_ORDERS_CSV_FAILED",
                ) from exc
            
            expected_columns = list(schema)
            if (
                len(header) != len(expected_columns)
                or set(header) != set(expected_columns)
            ):
                self._logger.error(
                    "Invalid columns in '%s'. Expected %s; received %s.",
                    source_path,expected_columns,header,
                )
                raise DataExtractionError(
                    f"Invalid columns in customer-orders file '{filename}'",
                    error_code="EXTRACT_CUSTOMER_ORDERS_SCHEMA_INVALID",
                )

            try:
                
                dataframe = pl.read_csv(
                    source_path,
                    schema_overrides=dict(schema),
                    infer_schema_length=0,
                    )
            except (pl.exceptions.PolarsError, OSError) as exc:
                self._logger.error(
                    "Customer-orders CSV extraction failed for '%s': %s",
                    source_path,
                    exc,
                )
                raise DataExtractionError(
                    f"Failed to extract customer-orders file '{filename}'",
                    error_code="EXTRACT_CUSTOMER_ORDERS_CSV_FAILED",
                ) from exc
            
            dataframes[filename] = dataframe.select(expected_columns)

            self._logger.info(
                "Extracted '%s': %d rows, %d columns.",
                filename,
                dataframe.height,
                dataframe.width,
            )
        self._logger.info(
            "Customer-orders CSV extraction completed successfully."
        )

        return CustomerOrdersBatch(
            customers=dataframes["customers.csv"],
            orders=dataframes["orders.csv"],
            order_lines=dataframes["order_lines.csv"],
        )