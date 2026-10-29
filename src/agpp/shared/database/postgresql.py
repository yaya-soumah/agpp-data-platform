"""Database access helpers that translate driver errors into AGPP errors."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection
from psycopg.rows import TupleRow
from psycopg_pool import PoolTimeout

from agpp.shared.database.pool import Pool
from agpp.shared.exceptions import DatabaseConnectionError, InfrastructureError


@contextmanager
def connection(pool: Pool) -> Iterator[Connection[TupleRow]]:
    """Borrow a connection; the transaction commits on success, rolls back on error.

    Connection and transaction failures become ``DatabaseConnectionError``
    (retryable). Other database errors become ``InfrastructureError``. AGPP
    errors raised inside the block pass through unchanged.
    """
    try:
        with pool.connection() as conn:
            yield conn
    except PoolTimeout as error:
        raise DatabaseConnectionError("Timed out waiting for a database connection") from error
    except psycopg.OperationalError as error:
        raise DatabaseConnectionError(
            "Database connection or transaction failed",
            context={"sqlstate": error.sqlstate},
        ) from error
    except psycopg.Error as error:
        raise InfrastructureError(
            "Database operation failed", context={"sqlstate": error.sqlstate}
        ) from error


def ping(pool: Pool) -> None:
    """Run a trivial query to prove the database answers."""
    with connection(pool) as conn:
        conn.execute("SELECT 1")
