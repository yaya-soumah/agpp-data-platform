from collections.abc import Iterator, Sequence

import polars as pl
from logging import Logger
from psycopg import Connection, DatabaseError, OperationalError, sql
from psycopg_pool import ConnectionPool
from src.pipelines.supplier_product.loader import (
    SupplierProductWarehouseLoader,
    WarehouseLoadResult,
)
from src.shared.configuration.models import PipelineConfig, WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError

_TABLE_NAME = "supplier_product"


class PostgreSQLSupplierProductWarehouseLoader(SupplierProductWarehouseLoader):
    """Loads supplier products into the PostgreSQL analytical warehouse."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        pipeline_config: PipelineConfig,
        warehouse_config: WarehouseConfig,
        logger: Logger
    ) -> None:
        self._pool = pool
        self._batch_size = pipeline_config.batch_size
        self._retry_attempts = pipeline_config.retry_attempts
        self._warehouse_config = warehouse_config
        self._logger = logger

    def load(self, products: pl.DataFrame) -> WarehouseLoadResult:
        """Load supplier products into the warehouse."""
        if products.is_empty():
            return WarehouseLoadResult(records_loaded=0)

        attempts = 0

        while True:
            try:
                return self._load_once(products)
            except InfrastructureError as exc:
                if not exc.retryable or attempts >= self._retry_attempts:
                    raise
                attempts += 1

                self._logger.warning(
                    "Supplier product warehouse load failed with a "
                    "retryable infrastructure error; retrying "
                    "(attempt %d/%d).",
                    attempts,
                    self._retry_attempts
                )
    
    def _load_once(self, products: pl.DataFrame) ->WarehouseLoadResult:

        rows = self._to_rows(products)

        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    for batch in self._batches(rows):
                        cursor.executemany(self._insert_sql(), batch)

            return WarehouseLoadResult(records_loaded=len(rows))

        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while loading "
                "supplier products into the warehouse.",
                error_code="WAREHOUSE_LOAD_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc

        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected supplier product warehouse data.",
                error_code="WAREHOUSE_LOAD_DATABASE_ERROR",
                retryable=False,
            ) from exc

    def _insert_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            INSERT INTO {}.{} (
                supplier_product_id,
                supplier_id,
                supplier_sku,
                name,
                description,
                price_amount,
                price_currency,
                minimum_order_quantity,
                lead_time_days
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """
        ).format(
            sql.Identifier(self._warehouse_config.warehouse_schema),
            sql.Identifier(_TABLE_NAME),
        )

    @staticmethod
    def _to_rows(products: pl.DataFrame) -> list[tuple[object, ...]]:
        return list(
            products.select(
                "supplier_product_id",
                "supplier_id",
                "supplier_sku",
                "name",
                "description",
                "price_amount",
                "price_currency",
                "minimum_order_quantity",
                "lead_time_days",
            ).iter_rows()
        )

    def _batches(
        self,
        rows: Sequence[tuple[object, ...]],
    ) -> Iterator[Sequence[tuple[object, ...]]]:
        batch_size = self._batch_size

        for start in range(0, len(rows), batch_size):
            yield rows[start : start + batch_size]
