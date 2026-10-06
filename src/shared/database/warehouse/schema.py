from psycopg import Connection, DatabaseError, OperationalError, sql
from psycopg_pool import ConnectionPool
from src.shared.configuration.models import WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError


class PostgreSQLWarehouseSchemaInitializer:
    """Initializes the PostgreSQL warehouse schema."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def initialize(self) -> None:
        """Create the warehouse schema if it does not exist."""
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(self._create_schema_sql())
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while initializing "
                "the warehouse schema.",
                error_code="WAREHOUSE_SCHEMA_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the warehouse schema initialization.",
                error_code="WAREHOUSE_SCHEMA_INITIALIZATION_FAILED",
                retryable=False,
            ) from exc

    def _create_schema_sql(self) -> sql.Composed:
        return sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
            sql.Identifier(self._warehouse_config.warehouse_schema)
        )
