"""Idempotent batch upserts into warehouse tables (ADR-0009)."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from psycopg import Connection, sql
from psycopg.rows import TupleRow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpsertResult:
    """How many rows were offered and how many were actually inserted or changed."""

    attempted: int
    written: int

    @property
    def unchanged(self) -> int:
        return self.attempted - self.written


def build_upsert_statement(
    *,
    schema: str,
    table: str,
    columns: Sequence[str],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str] | None = None,
    audit_column: str | None = "updated_at",
) -> sql.Composed:
    """Build ``INSERT ... ON CONFLICT`` that only writes rows whose values differ.

    ``update_columns=None`` updates every non-key column; an empty list never
    updates (existing rows are left alone). ``audit_column`` is set to ``now()``
    when a row changes; pass ``None`` for tables without one.
    """
    if not columns:
        raise ValueError("columns must not be empty")
    if not conflict_columns:
        raise ValueError("conflict_columns must not be empty")
    missing = [name for name in conflict_columns if name not in columns]
    if missing:
        raise ValueError(f"conflict columns not in columns: {missing}")
    if update_columns is None:
        update_columns = [name for name in columns if name not in conflict_columns]
    unknown = [name for name in update_columns if name not in columns]
    if unknown:
        raise ValueError(f"update columns not in columns: {unknown}")
    keys_updated = [name for name in update_columns if name in conflict_columns]
    if keys_updated:
        raise ValueError(f"key columns cannot be updated: {keys_updated}")

    head = sql.SQL(
        "INSERT INTO {target} ({columns}) VALUES ({values}) ON CONFLICT ({conflict}) "
    ).format(
        target=sql.Identifier(schema, table),
        columns=sql.SQL(", ").join(sql.Identifier(name) for name in columns),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        conflict=sql.SQL(", ").join(sql.Identifier(name) for name in conflict_columns),
    )
    if not update_columns:
        return head + sql.SQL("DO NOTHING")

    assignments = [
        sql.SQL("{name} = EXCLUDED.{name}").format(name=sql.Identifier(name))
        for name in update_columns
    ]
    if audit_column is not None:
        assignments.append(sql.SQL("{name} = now()").format(name=sql.Identifier(audit_column)))
    current = sql.SQL(", ").join(
        sql.SQL("{table}.{name}").format(table=sql.Identifier(table), name=sql.Identifier(name))
        for name in update_columns
    )
    incoming = sql.SQL(", ").join(
        sql.SQL("EXCLUDED.{name}").format(name=sql.Identifier(name)) for name in update_columns
    )
    return head + sql.SQL(
        "DO UPDATE SET {assignments} WHERE ({current}) IS DISTINCT FROM ({incoming})"
    ).format(
        assignments=sql.SQL(", ").join(assignments),
        current=current,
        incoming=incoming,
    )


def check_rows(rows: Sequence[Sequence[object]], width: int) -> None:
    """Fail early if any row does not have one value per column."""
    for index, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"row {index} has {len(row)} values, expected {width}")


def upsert(
    conn: Connection[TupleRow],
    *,
    schema: str,
    table: str,
    columns: Sequence[str],
    conflict_columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    update_columns: Sequence[str] | None = None,
    audit_column: str | None = "updated_at",
    batch_size: int = 1000,
) -> UpsertResult:
    """Upsert ``rows`` on ``conflict_columns`` using the caller's transaction.

    Running it again with the same rows writes nothing (Decision 13). If the
    same key appears twice in ``rows``, the later row wins. The caller owns the
    transaction, so a failure rolls back the whole load.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    statement = build_upsert_statement(
        schema=schema,
        table=table,
        columns=columns,
        conflict_columns=conflict_columns,
        update_columns=update_columns,
        audit_column=audit_column,
    )
    check_rows(rows, len(columns))

    written = 0
    if rows:
        with conn.cursor() as cursor:
            for start in range(0, len(rows), batch_size):
                cursor.executemany(statement, rows[start : start + batch_size])
                written += max(cursor.rowcount, 0)

    result = UpsertResult(attempted=len(rows), written=written)
    logger.info(
        "Upserted rows",
        extra={
            "table": f"{schema}.{table}",
            "attempted": result.attempted,
            "written": result.written,
            "unchanged": result.unchanged,
        },
    )
    return result
