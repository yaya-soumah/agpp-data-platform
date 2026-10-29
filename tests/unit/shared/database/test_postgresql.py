from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import psycopg
import pytest
from psycopg_pool import PoolTimeout

from agpp.shared.database.pool import Pool
from agpp.shared.database.postgresql import connection
from agpp.shared.exceptions import (
    DatabaseConnectionError,
    InfrastructureError,
    LoadingError,
)


class FakePool:
    """Mimics ``pool.connection()`` without a database."""

    def __init__(self, enter_error: Exception | None = None) -> None:
        self.enter_error = enter_error

    @contextmanager
    def connection(self) -> Iterator[str]:
        if self.enter_error is not None:
            raise self.enter_error
        yield "connection"


def _pool(enter_error: Exception | None = None) -> Pool:
    return cast(Pool, FakePool(enter_error))


def _use(pool: Pool) -> None:
    with connection(pool):
        pass


def _raise_inside(pool: Pool, error: Exception) -> None:
    with connection(pool):
        raise error


def test_yields_the_borrowed_connection() -> None:
    with connection(_pool()) as conn:
        assert str(conn) == "connection"


def test_pool_timeout_becomes_a_retryable_connection_error() -> None:
    with pytest.raises(DatabaseConnectionError) as info:
        _use(_pool(PoolTimeout("busy")))

    assert info.value.retryable is True
    assert isinstance(info.value.__cause__, PoolTimeout)


def test_operational_errors_inside_the_block_become_connection_errors() -> None:
    with pytest.raises(DatabaseConnectionError) as info:
        _raise_inside(_pool(), psycopg.OperationalError("connection lost"))

    assert info.value.retryable is True


def test_other_database_errors_are_not_retryable() -> None:
    error = psycopg.errors.UniqueViolation("duplicate key")

    with pytest.raises(InfrastructureError) as info:
        _raise_inside(_pool(), error)

    assert not isinstance(info.value, DatabaseConnectionError)
    assert info.value.retryable is False
    assert info.value.context == {"sqlstate": "23505"}


def test_agpp_errors_pass_through_unchanged() -> None:
    original = LoadingError("bad row", context={"row": 3})

    with pytest.raises(LoadingError) as info:
        _raise_inside(_pool(), original)

    assert info.value is original
