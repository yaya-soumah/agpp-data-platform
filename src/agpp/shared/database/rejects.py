"""Storage of rejected records in the operational schema (ADR-0012, ADR-0017)."""

from collections.abc import Sequence

from psycopg import Connection
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from agpp.shared.validation import RejectedRecord


def store_rejects(
    conn: Connection[TupleRow],
    *,
    run_id: str,
    pipeline: str,
    rejected: Sequence[RejectedRecord],
) -> int:
    """Store the rejects of a run in the caller's transaction; return how many were new.

    A line already stored for the same run, pipeline and source is left alone.
    """
    if not rejected:
        return 0
    rows = [
        (
            run_id,
            pipeline,
            record.source_id,
            record.line_number,
            record.stage.value,
            Jsonb(list(record.reasons)),
            Jsonb(dict(record.raw)),
        )
        for record in rejected
    ]
    with conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO operational.rejected_records"
            " (run_id, pipeline, source_id, line_number, stage, reasons, raw_values)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (run_id, pipeline, source_id, line_number) DO NOTHING",
            rows,
        )
        return max(cursor.rowcount, 0)
