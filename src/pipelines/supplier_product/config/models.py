from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.shared.exceptions import ConfigurationError


class SupplierProductSourceType(StrEnum):
    CSV = "csv"
    API = "api"
    FTP = "ftp"


class SupplierProductConfigModel(BaseModel):
    """Base model for all SUpplier Product pipeline configuration models"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CSVSourceConfig(SupplierProductConfigModel):
    """Configuration for a CSV source."""

    name: str = Field(min_length=1)
    type: Literal[SupplierProductSourceType.CSV]
    path: Path

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ConfigurationError(
                "Source name must not be blank.",
                error_code="CONFIG_SOURCE_NAME_VALIDATION_FAILED",
            )
        return value

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ConfigurationError(
                "source path must be relative to the raw data directory.",
                error_code="CONFIG_SOURCE_PATH_MUST_BE_RELATIVE",
            )
        return value


class APISourceConfig(SupplierProductConfigModel):
    """Configuration for an API source."""

    name: str = Field(min_length=1)
    type: Literal[SupplierProductSourceType.API]
    url: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ConfigurationError(
                "Source name must not be blank.",
                error_code="CONFIG_SOURCE_NAME_VALIDATION_FAILED",
            )
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.strip():
            raise ConfigurationError(
                "API URL must not be blank.",
                error_code="CONFIG_API_URL_VALIDATION_FAILED",
            )
        return value


class FTPSourceConfig(SupplierProductConfigModel):
    """Configuration for FTP source."""

    ...


class SupplierProductValidationConfig(SupplierProductConfigModel):
    """Validation configuration model."""

    reject_invalid_rows: bool = True


SupplierProductSourceConfig = CSVSourceConfig | APISourceConfig


class SupplierProductConfig(SupplierProductConfigModel):
    """Supplier product configuration."""

    sources: list[SupplierProductSourceConfig] = Field(min_length=1)
    validation: SupplierProductValidationConfig = SupplierProductValidationConfig()

    @field_validator("sources")
    @classmethod
    def validate_unique_source_name(
        cls, value: list[SupplierProductSourceConfig]
    ) -> list[SupplierProductSourceConfig]:
        names = [source.name for source in value]

        if len(names) != len(set(names)):
            raise ConfigurationError(
                "Source names must be unique.",
                error_code="CONFIG_SOURCE_NAMES_VALIDATION_FAILS",
            )
        return value
