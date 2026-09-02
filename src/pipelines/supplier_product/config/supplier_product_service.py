from pathlib import Path

from src.shared.configuration.loader import load_yaml_file
from src.shared.exceptions import ConfigurationError

from .models import (
    APISourceConfig,
    CSVSourceConfig,
    FTPSourceConfig,
    SupplierProductConfig,
)


class SupplierProductService:
    """Provides configuration for the supplier-product pipeline."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._config: SupplierProductConfig | None = None

    def get_config(self) -> SupplierProductConfig:
        """Load and return the supplier-product configuration."""

        if self._config is None:
            self._config = self._load_config()

        return self._config

    def load_csv_config(self) -> list[CSVSourceConfig]:
        """load and return all configuration CSV sources."""

        return [
            source
            for source in self.get_config().sources
            if isinstance(source, CSVSourceConfig)
        ]

    def load_api_config(self) -> list[APISourceConfig]:
        """load and return all configuration API sources."""

        return [
            source
            for source in self.get_config().sources
            if isinstance(source, APISourceConfig)
        ]

    def load_ftp_config(self) -> list[FTPSourceConfig]:
        """load and return all configuration API sources."""

        return [
            source
            for source in self.get_config().sources
            if isinstance(source, FTPSourceConfig)
        ]

    def _load_config(self) -> SupplierProductConfig:
        """Load and validate the supplier-product configuration."""

        if not self._config_path.is_file():
            raise ConfigurationError(
                "Supplier product configuration file does not exist.",
                error_code="CONFIG_SUPPLIER_PRODUCT_CONFIG_FILE_NOT_FOUND",
            )
        raw_config = load_yaml_file(self._config_path)

        try:
            return SupplierProductConfig.model_validate(raw_config)
        except ValueError as exc:
            raise ConfigurationError(
                "Invalid supplier product configuration.",
                error_code="CONFIG_SUPPLIER_PRODUCT_CONFIGURATION_INVALID",
            ) from exc
