import tempfile
from logging import Logger
from pathlib import Path

import aioftp
import polars as pl
from src.pipelines.supplier_product.config import FTPSourceConfig
from src.shared.configuration.models import AppConfig
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.exceptions import DataExtractionError


class FTPExtractor:
    """Extract supplier-product data from an FTP source."""

    def __init__(
        self,
        app_config: AppConfig,
        source_config: FTPSourceConfig,
        runtime_environment: RuntimeEnvironment,
        logger: Logger,
    ) -> None:
        self._app_config = app_config
        self._source_config = source_config
        self._runtime_environment = runtime_environment
        self._logger = logger

    async def extract(self) -> pl.DataFrame:
        """Download the configured FTP file and return it as a DataFrame."""

        retry_attempts = self._app_config.pipeline.retry_attempts

        password = self._runtime_environment.get_required_secret(
            self._source_config.password_env_var
        )

        self._logger.info(
            f"Starting FTP extraction for source '{self._source_config.name}' from "
            f"'{self._source_config.host}:{self._source_config.path.as_posix()}'"
        )

        for attempt in range(retry_attempts + 1):
            error_origin: Exception | None = None

            try:
                with tempfile.TemporaryDirectory() as temporary_directory:
                    local_path = (
                        Path(temporary_directory) / self._source_config.path.name
                    )

                    async with aioftp.Client.context(
                        self._source_config.host,
                        port=self._source_config.port,
                        user=self._source_config.username,
                        password=password.get_secret_value(),
                    ) as client:
                        await client.download(
                            self._source_config.path.as_posix(),
                            local_path.as_posix(),
                        )

                    dataframe = pl.read_csv(local_path)

                    self._logger.info(
                        f"FTP extraction completed for source '{self._source_config.name}': "
                        f"{dataframe.height} rows, {dataframe.width} columns."
                    )
                    return dataframe

            except aioftp.AIOFTPException as exc:
                self._logger.error(
                    f"FTP extraction failed for source '{self._source_config.name}': {exc}"
                )

                error = DataExtractionError(
                    "Failed to extract data from FTP source.",
                    error_code="EXTRACT_FTP_FAILED",
                    context={
                        "host": self._source_config.host,
                        "path": self._source_config.path.as_posix(),
                    },
                    retryable=True,
                )
                error_origin = exc

            except (OSError, ValueError) as exc:
                self._logger.error(
                    f"FTP source data processing failed for source '{self._source_config.name}': {exc}"
                )

                error = DataExtractionError(
                    "Failed to process FTP source data.",
                    error_code="EXTRACT_FTP_FAILED",
                    context={
                        "host": self._source_config.host,
                        "path": self._source_config.path.as_posix(),
                    },
                    retryable=False,
                )
                error_origin = exc

            self._logger.error(
                f"FTP extraction failed for source '{self._source_config.name}' "
                f"attempt {attempt + 1}/{retry_attempts + 1}: {error.message}"
            )

            if not error.retryable or attempt == retry_attempts:
                raise error from error_origin

        raise DataExtractionError(
            f"FTP extraction failed for source '{self._source_config.name}'",
            error_code="EXTRACT_FTP_FAILED",
            retryable=False,
        ) from error_origin
