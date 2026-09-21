from pydantic import BaseModel, SecretStr
from src.shared.configuration.models import DatabaseConfig
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.exceptions import ConfigurationError


class PostgreSQLConfig(BaseModel):
    """Runtime configuration required to connect to PostgreSQL."""

    host: str
    port: int
    database: str
    user: str
    password: SecretStr
    pool_size: int
    connection_timeout: int


class PostgreSQLConfigFactory:
    """Build PostgreSQL configuration from platform configuration runtime."""

    def __init__(
        self,
        database_config: DatabaseConfig,
        runtime_environment: RuntimeEnvironment,
    ) -> None:

        self._database_config = database_config
        self._runtime_environment = runtime_environment

    def create(self) -> PostgreSQLConfig:
        """Create PostgreSQL configuration."""

        return PostgreSQLConfig(
            host=self._runtime_environment.get_required("POSTGRES_HOST"),
            port=self._get_value(),
            database=self._runtime_environment.get_required("POSTGRES_DB"),
            user=self._runtime_environment.get_required("POSTGRES_USER"),
            password=self._runtime_environment.get_required_secret("POSTGRES_PASSWORD"),
            pool_size=self._database_config.pool_size,
            connection_timeout=self._database_config.connection_timeout,
        )

    def _get_value(self) -> int:
        """Read and validate PostgreSQL port."""

        value = self._runtime_environment.get_required("POSTGRES_PORT")

        try:
            return int(value)
        except ValueError as exc:
            raise ConfigurationError(
                "PostgreSQL Port value must be an integer.",
                error_code="CONFIG_POSTGRES_PORT_INVALID",
            ) from exc
