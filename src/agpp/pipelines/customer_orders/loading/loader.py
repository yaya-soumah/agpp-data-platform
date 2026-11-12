"""Load the validated, transformed order lines into the warehouse (ADR-0014, ADR-0016)."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from psycopg import Connection
from psycopg.rows import TupleRow

from agpp.pipelines.customer_orders import PIPELINE_NAME
from agpp.pipelines.customer_orders.transformation import TransformedOrders
from agpp.pipelines.customer_orders.validation import ValidationResult
from agpp.shared.database import Pool, connection
from agpp.shared.database.rejects import store_rejects
from agpp.shared.database.warehouse import UpsertResult, upsert
from agpp.shared.exceptions import (
    DatabaseConnectionError,
    InfrastructureError,
    LoadingError,
    WarehouseWriteError,
)
from agpp.shared.resilience.retry import RetryPolicy, call_with_retry

UNKNOWN_KEY = -1
CUSTOMER_COLUMNS = ["customer_id", "customer_name", "country", "source_updated_at"]
LINE_COLUMNS = [
    "order_id",
    "line_number",
    "customer_key",
    "product_key",
    "date_key",
    "quantity",
    "unit_price",
    "line_amount",
    "currency",
    "status",
    "ordered_at",
    "source_updated_at",
]
LINE_UPDATE_COLUMNS = [
    "customer_key",
    "product_key",
    "date_key",
    "quantity",
    "unit_price",
    "line_amount",
    "currency",
    "status",
    "ordered_at",
    "source_updated_at",
]


@dataclass(frozen=True)
class LoadResult:
    """What loading the order file changed."""

    lines_attempted: int
    lines_written: int
    lines_unchanged: int
    customers_written: int
    unknown_product_lines: int
    rejects_stored: int


def load_orders(
    pool: Pool,
    *,
    run_id: str,
    transformed: TransformedOrders,
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
            "Could not load the order lines",
            context={"sqlstate": error.context.get("sqlstate")},
        ) from error


def _load_once(
    pool: Pool, run_id: str, transformed: TransformedOrders, validation: ValidationResult
) -> LoadResult:
    with connection(pool) as conn:
        customers = upsert(
            conn,
            schema="warehouse",
            table="dim_customer",
            columns=CUSTOMER_COLUMNS,
            conflict_columns=["customer_id"],
            newer_column="source_updated_at",
            rows=[
                (c.customer_id, c.customer_name, c.country, c.source_updated_at)
                for c in transformed.customers
            ],
        )
        customer_keys = _customer_keys(conn, [c.customer_id for c in transformed.customers])
        product_keys = _product_keys(conn, sorted({line.product_id for line in transformed.lines}))

        rows: list[tuple[object, ...]] = []
        unknown_product_lines = 0
        for line in transformed.lines:
            customer_key = customer_keys.get(line.customer_id)
            if customer_key is None:
                raise LoadingError(
                    "Customer row missing right after its upsert",
                    context={"customer_id": line.customer_id},
                )
            product_key = product_keys.get(line.product_id, UNKNOWN_KEY)
            if product_key == UNKNOWN_KEY:
                unknown_product_lines += 1
            rows.append(
                (
                    line.order_id,
                    line.line_number,
                    customer_key,
                    product_key,
                    line.date_key,
                    line.quantity,
                    line.unit_price,
                    line.line_amount,
                    line.currency,
                    line.status,
                    line.ordered_at,
                    line.source_updated_at,
                )
            )

        lines = upsert(
            conn,
            schema="warehouse",
            table="fact_order_line",
            columns=LINE_COLUMNS,
            conflict_columns=["order_id", "line_number"],
            update_columns=LINE_UPDATE_COLUMNS,
            newer_column="source_updated_at",
            rows=rows,
        )
        rejects_stored = store_rejects(
            conn, run_id=run_id, pipeline=PIPELINE_NAME, rejected=validation.rejected
        )
        _record_result(conn, run_id, validation, lines, unknown_product_lines)

    return LoadResult(
        lines_attempted=lines.attempted,
        lines_written=lines.written,
        lines_unchanged=lines.unchanged,
        customers_written=customers.written,
        unknown_product_lines=unknown_product_lines,
        rejects_stored=rejects_stored,
    )


def _customer_keys(conn: Connection[TupleRow], customer_ids: list[str]) -> dict[str, int]:
    if not customer_ids:
        return {}
    rows = conn.execute(
        "SELECT customer_id, customer_key FROM warehouse.dim_customer WHERE customer_id = ANY(%s)",
        (customer_ids,),
    ).fetchall()
    return {str(customer_id): int(key) for customer_id, key in rows}


def _product_keys(conn: Connection[TupleRow], product_ids: list[str]) -> dict[str, int]:
    """Look products up; they belong to the Supplier Product pipeline and are never written here."""
    if not product_ids:
        return {}
    rows = conn.execute(
        "SELECT product_id, product_key FROM warehouse.dim_product WHERE product_id = ANY(%s)",
        (product_ids,),
    ).fetchall()
    return {str(product_id): int(key) for product_id, key in rows}


def _record_result(
    conn: Connection[TupleRow],
    run_id: str,
    validation: ValidationResult,
    lines: UpsertResult,
    unknown_product_lines: int,
) -> None:
    conn.execute(
        "INSERT INTO operational.order_run_results (run_id, status, rows_read, valid_rows,"
        " rejected_rows, lines_written, lines_unchanged, unknown_product_lines)"
        " VALUES (%s, 'loaded', %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (run_id) DO UPDATE SET status = 'loaded', failed_stage = NULL,"
        " error_message = NULL, rows_read = EXCLUDED.rows_read, valid_rows = EXCLUDED.valid_rows,"
        " rejected_rows = EXCLUDED.rejected_rows, lines_written = EXCLUDED.lines_written,"
        " lines_unchanged = EXCLUDED.lines_unchanged,"
        " unknown_product_lines = EXCLUDED.unknown_product_lines, recorded_at = now()",
        (
            run_id,
            validation.rows_read,
            len(validation.valid),
            len(validation.rejected),
            lines.written,
            lines.unchanged,
            unknown_product_lines,
        ),
    )
