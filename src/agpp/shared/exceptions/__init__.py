"""Exception hierarchy for the AGPP platform."""

from agpp.shared.exceptions.base import AgppError
from agpp.shared.exceptions.configuration import (
    ConfigurationError,
    ConfigurationFileError,
    InvalidConfigurationError,
    MissingEnvironmentVariableError,
)
from agpp.shared.exceptions.extraction import (
    ExtractionError,
    SourceUnavailableError,
    UnsupportedSourceError,
)
from agpp.shared.exceptions.infrastructure import (
    DatabaseConnectionError,
    InfrastructureError,
    MigrationError,
    TransientInfrastructureError,
)
from agpp.shared.exceptions.loading import LoadingError, WarehouseWriteError
from agpp.shared.exceptions.transformation import TransformationError
from agpp.shared.exceptions.validation import (
    DataValidationError,
    QualityThresholdExceededError,
    SchemaValidationError,
)

__all__ = [
    "AgppError",
    "ConfigurationError",
    "ConfigurationFileError",
    "DataValidationError",
    "DatabaseConnectionError",
    "ExtractionError",
    "InfrastructureError",
    "InvalidConfigurationError",
    "LoadingError",
    "MigrationError",
    "MissingEnvironmentVariableError",
    "QualityThresholdExceededError",
    "SchemaValidationError",
    "SourceUnavailableError",
    "TransformationError",
    "TransientInfrastructureError",
    "UnsupportedSourceError",
    "WarehouseWriteError",
]
