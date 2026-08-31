from logging import Logger

import httpx
import polars as pl
from src.pipelines.supplier_product.config import APISourceConfig
from src.shared.configuration.models import AppConfig
from src.shared.exceptions import DataExtractionError


class APIExtractor:
    """Extract supplier-product data from an HTTP API."""

    def __init__(
        self, app_config: AppConfig, source_config: APISourceConfig, logger: Logger
    ) -> None:
        self._app_config = app_config
        self._source_config = source_config
        self._logger = logger

    async def extract(self) -> pl.DataFrame:
        """Extract API data into a Polars DataFrame."""

        retry_attempts = self._app_config.pipeline.retry_attempts

        self._logger.info(
            f"Starting API extraction for source '{self._source_config.name}' from '{self._source_config.url}'"
        )

        async with httpx.AsyncClient() as client:
            for attempt in range(retry_attempts + 1):
                error_origin: Exception | None = None

                try:
                    response = await client.get(self._source_config.url)
                    response.raise_for_status()

                    data = response.json()
                    dataframe = pl.DataFrame(data)

                    self._logger.info(
                        f"API extraction completed for source '{self._source_config.name}': {dataframe.height} rows, {dataframe.width} columns."
                    )
                    return dataframe

                except httpx.TimeoutException as exc:
                    self._logger.error(
                        f"API extraction timed out for source '{self._source_config.name}': {exc}"
                    )
                    error = DataExtractionError(
                        f"API extraction timed out for source '{self._source_config.name}'.",
                        error_code="EXTRACT_API_TIMEOUT",
                        retryable=True,
                    )
                    error_origin = exc

                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code

                    retryable = 500 <= status_code < 600

                    self._logger.error(
                        f"API extraction failed for source '{self._source_config.name}' with HTTP status {status_code}: {exc}"
                    )

                    error = DataExtractionError(
                        f"API extraction failed for source '{self._source_config.name}' with HTTP status {status_code}",
                        error_code="EXTRACT_API_HTTP_ERROR",
                        retryable=retryable,
                    )
                    error_origin = exc

                except httpx.RequestError as exc:
                    self._logger.error(
                        f"API extraction failed for source '{self._source_config.name}': {exc}"
                    )

                    error = DataExtractionError(
                        "API extraction failed for source '{self._source_config.name}'",
                        error_code="EXTRACT_API_REQUEST_FAILED",
                        retryable=True,
                    )
                    error_origin = exc

                except (ValueError, pl.exceptions.PolarsError) as exc:
                    self._logger.error(
                        f"API response procession failed for source '{self._source_config.name}': {exc}"
                    )

                    error = DataExtractionError(
                        f"API response procession failed for source '{self._source_config.name}'",
                        error_code="EXTRACT_API_RESPONSE_INVALID",
                        retryable=False,
                    )
                    error_origin = exc

                self._logger.error(
                    f"API extraction failed for source '{self._source_config.name}' attempt {attempt + 1}/{retry_attempts + 1}: {error.message}"
                )

                if not error.retryable or attempt == retry_attempts:
                    raise error from error_origin

        raise DataExtractionError(
            f"API extraction failed for source '{self._source_config.name}'",
            error_code="EXTRACT_API_FAILED",
            retryable=False,
        ) from error_origin
