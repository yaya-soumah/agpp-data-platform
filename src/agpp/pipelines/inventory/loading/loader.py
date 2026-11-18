"""Load the validated, transformed stock snapshot into the warehouse (ADR-0014, ADR-0018)."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from psycopg import Connection
from psycopg.rows import TupleRow

from agpp.pipelines.inventory import PIPELINE_NAME
from agpp.pipelines.inventory.transformation import TransformedInventory
from agpp.pipelines.inventory.validation import ValidationResult
from agpp.shared.database import Pool, connection
from agpp.shared.database.rejects import store_rejects
from agpp.shared.database.warehouse import UpsertResult, resolve_keys, upsert
from agpp.shared.exceptions import (
    DatabaseConnectionError,
    InfrastructureError,
    LoadingError,
    WarehouseWriteError,
)
from agpp.shared.resilience.retry import RetryPolicy, call_with_retry

UNKNOWN_KEY = -1
LOCATION_COLUMNS = ["location_code", "location_name", "country", "source_updated_at"]
SNAPSHOT_COLUMNS = [
    "date_key",
    "location_key",
    "product_id",
    "product_key",
    "on_hand",
    "reserved",
    "available",
    "reorder_point",
    "below_reorder_point",
    "snapshot_at",
    "source_updated_at",
]
SNAPSHOT_UPDATE_COLUMNS = [
    "product_key",
    "on_hand",
    "reserved",
    "available",
    "reorder_point",
    "below_reorder_point",
    "snapshot_at",
    "source_updated_at",
]


@dataclass(frozen=True)
class LoadResult:
    """What loading the snapshot changed."""

    rows_attempted: int
    rows_written: int
    rows_unchanged: int
    locations_written: int
    unknown_product_rows: int
    below_reorder_rows: int
    rejects_stored: int


def load_inventory(
    pool: Pool,
    *,
    run_id: str,
    transformed: TransformedInventory,
    validation: ValidationResult,
    retry_policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> LoadResult:
    """Load the whole run in a single transaction, retrying lost connections.

    Raises ``DatabaseConnectionError`` if the database stays unreachable and
    ``WarehouseWriteError`` for any other database failure. Nothing is written
    in either case.
    """
    policy = retry_policy or RetryPolicy()
    try:
        return call_with_retry(
            lambda: _load_once(pool, run_id, transformed, validation), policy, sleep=sleep
        )
    except DatabaseConnectionError:
        raise
    except InfrastructureError as error:
        raise WarehouseWriteError(
            "Could not load the stock snapshot",
            context={"sqlstate": error.context.get("sqlstate")},
        ) from error


def _load_once(
    pool: Pool, run_id: str, transformed: TransformedInventory, validation: ValidationResult
) -> LoadResult:
    with connection(pool) as conn:
        locations = upsert(
            conn,
            schema="warehouse",
            table="dim_location",
            columns=LOCATION_COLUMNS,
            conflict_columns=["location_code"],
            newer_column="source_updated_at",
            rows=[
                (loc.location_code, loc.location_name, loc.country, loc.source_updated_at)
                for loc in transformed.locations
            ],
        )
        location_keys = resolve_keys(
            conn,
            schema="warehouse",
            table="dim_location",
            business_key="location_code",
            surrogate_key="location_key",
            values=[loc.location_code for loc in transformed.locations],
        )
        product_keys = resolve_keys(
            conn,
            schema="warehouse",
            table="dim_product",
            business_key="product_id",
            surrogate_key="product_key",
            values=sorted({row.product_id for row in transformed.rows}),
        )

        rows: list[tuple[object, ...]] = []
        unknown_product_rows = 0
        for row in transformed.rows:
            location_key = location_keys.get(row.location_code)
            if location_key is None:
                raise LoadingError(
                    "Location row missing right after its upsert",
                    context={"location_code": row.location_code},
                )
            product_key = product_keys.get(row.product_id, UNKNOWN_KEY)
            if product_key == UNKNOWN_KEY:
                unknown_product_rows += 1
            rows.append(
                (
                    transformed.date_key,
                    location_key,
                    row.product_id,
                    product_key,
                    row.on_hand,
                    row.reserved,
                    row.available,
                    row.reorder_point,
                    row.below_reorder_point,
                    transformed.snapshot_at,
                    row.source_updated_at,
                )
            )

        snapshot = upsert(
            conn,
            schema="warehouse",
            table="fact_inventory_snapshot",
            columns=SNAPSHOT_COLUMNS,
            conflict_columns=["date_key", "location_key", "product_id"],
            update_columns=SNAPSHOT_UPDATE_COLUMNS,
            newer_column="snapshot_at",
            rows=rows,
        )
        below_reorder_rows = sum(1 for row in transformed.rows if row.below_reorder_point)
        rejects_stored = store_rejects(
            conn, run_id=run_id, pipeline=PIPELINE_NAME, rejected=validation.rejected
        )
        _record_result(conn, run_id, validation, snapshot, unknown_product_rows, below_reorder_rows)

    return LoadResult(
        rows_attempted=snapshot.attempted,
        rows_written=snapshot.written,
        rows_unchanged=snapshot.unchanged,
        locations_written=locations.written,
        unknown_product_rows=unknown_product_rows,
        below_reorder_rows=below_reorder_rows,
        rejects_stored=rejects_stored,
    )


def _record_result(
    conn: Connection[TupleRow],
    run_id: str,
    validation: ValidationResult,
    snapshot: UpsertResult,
    unknown_product_rows: int,
    below_reorder_rows: int,
) -> None:
    conn.execute(
        "INSERT INTO operational.inventory_run_results (run_id, status, snapshot_at, rows_read,"
        " valid_rows, rejected_rows, rows_written, rows_unchanged, unknown_product_rows,"
        " below_reorder_rows)"
        " VALUES (%s, 'loaded', %s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (run_id) DO UPDATE SET status = 'loaded', failed_stage = NULL,"
        " error_message = NULL, snapshot_at = EXCLUDED.snapshot_at,"
        " rows_read = EXCLUDED.rows_read, valid_rows = EXCLUDED.valid_rows,"
        " rejected_rows = EXCLUDED.rejected_rows, rows_written = EXCLUDED.rows_written,"
        " rows_unchanged = EXCLUDED.rows_unchanged,"
        " unknown_product_rows = EXCLUDED.unknown_product_rows,"
        " below_reorder_rows = EXCLUDED.below_reorder_rows, recorded_at = now()",
        (
            run_id,
            validation.snapshot_at,
            validation.rows_read,
            len(validation.valid),
            len(validation.rejected),
            snapshot.written,
            snapshot.unchanged,
            unknown_product_rows,
            below_reorder_rows,
        ),
    )
