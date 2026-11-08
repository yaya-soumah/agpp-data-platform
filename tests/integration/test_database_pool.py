from collections.abc import Iterator

import pytest

from agpp.shared.configuration.models import DatabaseConfig
from agpp.shared.database import Pool, connection, create_pool, ping
from agpp.shared.exceptions import DatabaseConnectionError
from agpp.shared.resilience.retry import RetryPolicy


@pytest.fixture
def pool(database_config: DatabaseConfig) -> Iterator[Pool]:
    created = create_pool(database_config)
    yield created
    created.close()


def test_pool_serves_queries(pool: Pool) -> None:
    with connection(pool) as conn:
        row = conn.execute("SELECT 1").fetchone()

    assert row == (1,)


def test_ping_succeeds(pool: Pool) -> None:
    ping(pool)


def test_unreachable_database_raises_a_connection_error(
    database_config: DatabaseConfig,
) -> None:
    unreachable = database_config.model_copy(update={"port": 1, "connect_timeout_seconds": 1})

    with pytest.raises(DatabaseConnectionError):
        create_pool(unreachable, retry_policy=RetryPolicy(max_attempts=1))
