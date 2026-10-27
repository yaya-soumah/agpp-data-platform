"""Typed, immutable platform configuration."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from agpp.shared.configuration.environment import Environment


class FrozenModel(BaseModel):
    """Base for configuration models: immutable, unknown keys rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class AppConfig(FrozenModel):
    name: str
    debug: bool = False


class DatabaseConfig(FrozenModel):
    host: str
    port: int = Field(ge=1, le=65535)
    name: str
    user: str
    password: SecretStr
    pool_min_size: int = Field(ge=1)
    pool_max_size: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_pool_sizes(self) -> Self:
        if self.pool_min_size > self.pool_max_size:
            raise ValueError("pool_min_size must not exceed pool_max_size")
        return self


class LoggingConfig(FrozenModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["console", "json"] = "console"
    file: str | None = None
    file_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    file_backup_count: int = Field(default=5, ge=0)


class PlatformConfig(FrozenModel):
    environment: Environment
    app: AppConfig
    database: DatabaseConfig
    logging: LoggingConfig
