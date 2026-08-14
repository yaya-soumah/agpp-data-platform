from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .environment import Environment

class ConfigurationModel(BaseModel):
    """Base model for all AGPP configuration models"""

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        strict=True
    )


class ApplicationConfig(ConfigurationModel):
    """Application metadata configuration."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)

class EnvironmentConfig(ConfigurationModel):
    """Runtime environment configuration."""

    timezone: str = Field(min_length=1)


class PipelineConfig(ConfigurationModel):
    """Pipeline execution configuration."""

    batch_size: int = Field(gt=0)
    retry_attempts: int = Field(ge=0)

class WarehouseConfig(ConfigurationModel):
    """Analytical warehouse configuration."""

    schema: str = Field(min_length=1)

class DatabaseConfig(ConfigurationModel):
    """Database connection and pool configuration."""

    port: int = Field(ge=1,le=65535)
    pool_size: int = Field(gt=0)
    connection_timeout: int = Field(gt=0)

class PathsConfig(ConfigurationModel):
    """Application data path configuration."""

    raw_data: str =Field(min_length=1)
    processed_data: str = Field(min_length=1)
    archive_data: str = Field(min_length=1)

class FeaturesConfig(ConfigurationModel):
    """Application feature flags."""

    enable_metrics: bool
    enable_profiling: bool

class AppConfig(ConfigurationModel):
    """Complete validated application configuration"""

    application: ApplicationConfig
    environment_name: Environment
    environment: EnvironmentConfig
    pipeline: PipelineConfig
    warehouse: WarehouseConfig
    database: DatabaseConfig
    paths: PathsConfig
    features: FeaturesConfig

class LoggingFormatConfig(ConfigurationModel):
    """Logging format configuration."""

    standard: str = Field(min_length=1)


class ConsoleHandlerConfig(ConfigurationModel):
    """Console logging handler configuration."""

    enabled: bool

class FileHandlerConfig(ConfigurationModel):
    """File logging handler configuration."""

    enabled: bool
    path: str = Field(min_length=1)

class LoggingHandlersConfig(ConfigurationModel):
    """Logging handlers configuration."""

    console: ConsoleHandlerConfig
    file: FileHandlerConfig


class LoggingEnvironmentLevelConfig(ConfigurationModel):
    """Environment-specific logging levels."""

    level: Literal["DEBUG","WARNING","INFO","ERROR","CRITICAL"] = Field(min_length=1, description="Logging level")

class LoggingConfig(ConfigurationModel):
    """Complete validated logging configuration."""

    version: int = Field(gt=0)
    format: LoggingFormatConfig
    handlers: LoggingHandlersConfig
    development: LoggingEnvironmentLevelConfig
    testing: LoggingEnvironmentLevelConfig
    production: LoggingEnvironmentLevelConfig


