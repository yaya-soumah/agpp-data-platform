from psycopg import Connection
from psycopg_pool import ConnectionPool
from src.shared.database.postgresql import PostgreSQLConfig


def create_postgresql_pool(
    config: PostgreSQLConfig,
) -> ConnectionPool[Connection]:
    """Create a PostgreSQL connection pool."""

    return ConnectionPool(
        conninfo=(
            f"host={config.host} "
            f"port={config.port} "
            f"dbname={config.database} "
            f"user={config.user} "
            f"password={config.password.get_secret_value()}"
        ),
        min_size=1,
        max_size=config.pool_size,
        timeout=config.connection_timeout,
        open=False,
    )
