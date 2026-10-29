"""PostgreSQL connection pool."""

import time
from collections.abc import Callable

from psycopg import Connection
from psycopg.conninfo import make_conninfo
from psycopg.rows import TupleRow
from psycopg_pool import ConnectionPool, PoolTimeout

from agpp.shared.configuration.models import DatabaseConfig
from agpp.shared.exceptions import DatabaseConnectionError
from agpp.shared.resilience.retry import RetryPolicy, call_with_retry

type Pool = ConnectionPool[Connection[TupleRow]]


def build_conninfo(config: DatabaseConfig) -> str:
    """Return a libpq connection string. It contains the password: never log it."""
    return make_conninfo(
        host=config.host,
        port=config.port,
        dbname=config.name,
        user=config.user,
        password=config.password.get_secret_value(),
        connect_timeout=config.connect_timeout_seconds,
    )


def create_pool(
    config: DatabaseConfig,
    *,
    retry_policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Pool:
    """Open a connection pool, retrying while the database is unreachable."""
    policy = retry_policy or RetryPolicy()
    return call_with_retry(lambda: _open_pool(config), policy, sleep=sleep)


def _open_pool(config: DatabaseConfig) -> Pool:
    pool: Pool = ConnectionPool(
        build_conninfo(config),
        min_size=config.pool_min_size,
        max_size=config.pool_max_size,
        open=False,
    )
    try:
        pool.open(wait=True, timeout=config.connect_timeout_seconds)
    except PoolTimeout as error:
        pool.close()
        raise DatabaseConnectionError(
            "Could not connect to the database",
            context={"host": config.host, "port": config.port, "database": config.name},
        ) from error
    return pool
