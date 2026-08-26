from pathlib import Path

from src.shared.configuration.loader import load_yaml_file
from src.shared.exceptions import ConfigurationError

from .models import SupplierProductConfig


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

    def _load_config(self) -> SupplierProductConfig:
        """Load and validate the supplier-product configuration."""

        if not self._config_path.is_file():
            raise ConfigurationError(
                "Supplier product configuration file does not exist.",
                error_code="CONFIG_PIPELINE_FILE_NOT_FOUND",
            )

        raw_config = load_yaml_file(self._config_path)

        try:
            return SupplierProductConfig.model_validate(raw_config)
        except ValueError as exc:
            raise ConfigurationError(
                "Invalid supplier product configuration.",
                error_code="CONFIG_PIPELINE_INVALID",
            ) from exc
