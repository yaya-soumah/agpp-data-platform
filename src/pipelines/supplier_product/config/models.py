from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.shared.exceptions import ConfigurationError


class SupplierProductSourceType(StrEnum):
    CSV = "csv"


class SupplierProductConfigModel(BaseModel):
    """Base model for all SUpplier Product pipeline configuration models"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SupplierProductSourceConfig(SupplierProductConfigModel):
    """Source configuration model."""

    name: str = Field(min_length=1)
    type: SupplierProductSourceType
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


class SupplierProductValidationConfig(SupplierProductConfigModel):
    """Validation Configuration model"""

    reject_invalid_rows: bool = True


class SupplierProductConfig(SupplierProductConfigModel):
    """Supplier Product configuration."""

    sources: list[SupplierProductSourceConfig] = Field(min_length=1)
    validation: SupplierProductValidationConfig = SupplierProductValidationConfig()

    @field_validator("sources")
    @classmethod
    def validate_unique_source_names(
        cls, value: list[SupplierProductSourceConfig]
    ) -> list[SupplierProductSourceConfig]:
        names = [source.name for source in value]

        if len(names) != len(set(names)):
            raise ConfigurationError(
                "Source names must be unique.",
                error_code="CONFIG_SOURCE_NAMES_VALIDATION_ERROR",
            )

        return value
