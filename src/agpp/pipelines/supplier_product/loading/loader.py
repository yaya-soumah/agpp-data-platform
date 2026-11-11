"""Load one supplier's validated, transformed data into the warehouse (ADR-0014)."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from psycopg import Connection
from psycopg.rows import TupleRow

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.pipelines.supplier_product.transformation import TransformedBatch
from agpp.pipelines.supplier_product.validation import ValidationResult
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

SUPPLIER_COLUMNS = ["supplier_id", "supplier_name", "country"]
PRODUCT_COLUMNS = [
    "product_id",
    "supplier_key",
    "supplier_sku",
    "product_name",
    "category",
    "unit_price",
    "currency",
    "min_order_quantity",
    "lead_time_days",
    "is_active",
    "source_updated_at",
]
PRODUCT_UPDATE_COLUMNS = [
    "product_name",
    "category",
    "unit_price",
    "currency",
    "min_order_quantity",
    "lead_time_days",
    "is_active",
    "source_updated_at",
]


@dataclass(frozen=True)
class LoadResult:
    """What loading one supplier changed."""

    supplier_id: str
    products_attempted: int
    products_written: int
    products_unchanged: int
    rejects_stored: int


def load_supplier(
    pool: Pool,
    *,
    run_id: str,
    batch: TransformedBatch,
    validation: ValidationResult,
    retry_policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> LoadResult:
    """Load one supplier in a single transaction, retrying lost connections.

    Raises ``DatabaseConnectionError`` if the database stays unreachable and
    ``WarehouseWriteError`` for any other database failure. Nothing is written
    in either case.
    """
    supplier_id = batch.supplier.supplier_id
    policy = retry_policy or RetryPolicy()
    try:
        return call_with_retry(
            lambda: _load_once(pool, run_id, batch, validation), policy, sleep=sleep
        )
    except DatabaseConnectionError:
        raise
    except InfrastructureError as error:
        raise WarehouseWriteError(
            f"Could not load supplier {supplier_id}",
            context={"supplier_id": supplier_id, "sqlstate": error.context.get("sqlstate")},
        ) from error


def _load_once(
    pool: Pool, run_id: str, batch: TransformedBatch, validation: ValidationResult
) -> LoadResult:
    supplier = batch.supplier
    with connection(pool) as conn:
        upsert(
            conn,
            schema="warehouse",
            table="dim_supplier",
            columns=SUPPLIER_COLUMNS,
            conflict_columns=["supplier_id"],
            rows=[(supplier.supplier_id, supplier.supplier_name, supplier.country)],
        )
        supplier_key = _supplier_key(conn, supplier.supplier_id)
        products = upsert(
            conn,
            schema="warehouse",
            table="dim_product",
            columns=PRODUCT_COLUMNS,
            conflict_columns=["product_id"],
            update_columns=PRODUCT_UPDATE_COLUMNS,
            newer_column="source_updated_at",
            rows=[
                (
                    row.product_id,
                    supplier_key,
                    row.supplier_sku,
                    row.product_name,
                    row.category,
                    row.unit_price,
                    row.currency,
                    row.min_order_quantity,
                    row.lead_time_days,
                    row.is_active,
                    row.source_updated_at,
                )
                for row in batch.products
            ],
        )
        rejects_stored = store_rejects(
            conn, run_id=run_id, pipeline=PIPELINE_NAME, rejected=validation.rejected
        )
        _record_result(conn, run_id, supplier.supplier_id, validation, products)
    return LoadResult(
        supplier_id=supplier.supplier_id,
        products_attempted=products.attempted,
        products_written=products.written,
        products_unchanged=products.unchanged,
        rejects_stored=rejects_stored,
    )


def _supplier_key(conn: Connection[TupleRow], supplier_id: str) -> int:
    row = conn.execute(
        "SELECT supplier_key FROM warehouse.dim_supplier WHERE supplier_id = %s", (supplier_id,)
    ).fetchone()
    if row is None:
        raise LoadingError(
            "Supplier row missing right after its upsert", context={"supplier_id": supplier_id}
        )
    return int(row[0])


def _record_result(
    conn: Connection[TupleRow],
    run_id: str,
    supplier_id: str,
    validation: ValidationResult,
    products: UpsertResult,
) -> None:
    conn.execute(
        "INSERT INTO operational.supplier_run_results (run_id, supplier_id, status, rows_read,"
        " valid_rows, rejected_rows, products_written, products_unchanged)"
        " VALUES (%s, %s, 'loaded', %s, %s, %s, %s, %s)"
        " ON CONFLICT (run_id, supplier_id) DO UPDATE SET status = 'loaded',"
        " failed_stage = NULL, error_message = NULL, rows_read = EXCLUDED.rows_read,"
        " valid_rows = EXCLUDED.valid_rows, rejected_rows = EXCLUDED.rejected_rows,"
        " products_written = EXCLUDED.products_written,"
        " products_unchanged = EXCLUDED.products_unchanged, recorded_at = now()",
        (
            run_id,
            supplier_id,
            validation.rows_read,
            len(validation.valid),
            len(validation.rejected),
            products.written,
            products.unchanged,
        ),
    )
