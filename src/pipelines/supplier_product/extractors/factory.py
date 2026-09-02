from logging import Logger

from src.pipelines.supplier_product.config import (
    APISourceConfig,
    CSVSourceConfig,
    FTPSourceConfig,
    SupplierProductSourceConfig,
)
from src.pipelines.supplier_product.extractors.api import APIExtractor
from src.pipelines.supplier_product.extractors.base import SupplierProductExtractor
from src.pipelines.supplier_product.extractors.csv import CSVExtractor
from src.pipelines.supplier_product.extractors.ftp import FTPExtractor
from src.shared.configuration.models import AppConfig
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.exceptions import ConfigurationError


class SupplierProductExtractorFactory:
    """Create supplier-product extractors from source configuration."""

    def __init__(
        self,
        app_config: AppConfig,
        runtime_environment: RuntimeEnvironment,
        logger: Logger,
    ) -> None:
        self._app_config = app_config
        self._runtime_environment = runtime_environment
        self._logger = logger

    def create(
        self, source_config: SupplierProductSourceConfig
    ) -> SupplierProductExtractor:
        """Create an extractor for the configured source type."""

        if isinstance(source_config, CSVSourceConfig):
            return CSVExtractor(
                app_config=self._app_config,
                source_config=source_config,
                logger=self._logger,
            )

        if isinstance(source_config, APISourceConfig):
            return APIExtractor(
                app_config=self._app_config,
                source_config=source_config,
                logger=self._logger,
            )

        if isinstance(source_config, FTPSourceConfig):
            return FTPExtractor(
                app_config=self._app_config,
                source_config=source_config,
                runtime_environment=self._runtime_environment,
                logger=self._logger,
            )

        raise ConfigurationError(
            f"Unsupported supplier-product source configuration: {type(source_config).__name__}",
            error_code="UNSUPPORTED_SOURCE_CONFIG",
        )
