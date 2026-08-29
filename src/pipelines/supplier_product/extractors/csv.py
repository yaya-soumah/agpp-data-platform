from logging import Logger
from pathlib import Path

import polars as pl
from src.pipelines.supplier_product.config import SupplierProductSourceConfig
from src.shared.configuration.models import AppConfig
from src.shared.exceptions import DataExtractionError


class CSVExtractor:
    """Extract supplier-product data from a CSV source."""

    def __init__(
        self,
        app_config: AppConfig,
        source_config: SupplierProductSourceConfig,
        logger: Logger,
    ) -> None:
        self._app_config = app_config
        self._source_config = source_config
        self._logger = logger

    def extract(self) -> pl.DataFrame:
        """Extract CSV data into a Polars DataFrame."""

        source_path = Path(self._app_config.paths.raw_data) / self._source_config.path

        self._logger.info(
            f"Starting CSV extraction for source "
            f"'{self._source_config.name}' from '{source_path}'.",
        )

        try:
            dataframe = pl.read_csv(source_path)
        except (pl.exceptions.PolarsError, OSError) as exc:
            self._logger.error(
                f"CSV extraction failed for source "
                f"'{self._source_config.name}' at '{source_path}': {exc} ",
            )
            raise DataExtractionError(
                f"Failed to extract CSV source '{self._source_config.name}'",
                error_code="EXTRACT_CSV_FAILED",
            ) from exc

        self._logger.info(
            f"CSV extraction completed for source "
            f"'{self._source_config.name}': {dataframe.height} rows, {dataframe.width} columns."
        )

        return dataframe
