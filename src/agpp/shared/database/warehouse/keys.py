"""Resolve business keys to surrogate keys (ADR-0009, ADR-0017)."""

from collections.abc import Sequence

from psycopg import Connection, sql
from psycopg.rows import TupleRow


def resolve_keys(
    conn: Connection[TupleRow],
    *,
    schema: str,
    table: str,
    business_key: str,
    surrogate_key: str,
    values: Sequence[str],
) -> dict[str, int]:
    """Map business keys to surrogate keys using the caller's transaction.

    Keys that do not exist are absent from the result, so the caller decides what
    that means (a missing customer is a bug, a missing product is the unknown member).
    """
    if not values:
        return {}
    query = sql.SQL(
        "SELECT {business}, {surrogate} FROM {table} WHERE {business} = ANY(%s)"
    ).format(
        business=sql.Identifier(business_key),
        surrogate=sql.Identifier(surrogate_key),
        table=sql.Identifier(schema, table),
    )
    rows = conn.execute(query, (list(values),)).fetchall()
    return {str(business): int(key) for business, key in rows}
