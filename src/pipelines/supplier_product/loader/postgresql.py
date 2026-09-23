from collections.abc import Iterator, Sequence

import polars as pl
from logging import Logger
from psycopg import Connection, DatabaseError, OperationalError
from psycopg_pool import ConnectionPool
from src.pipelines.supplier_product.loader import LoadResult
from src.shared.configuration.models import PipelineConfig
from src.shared.exceptions import InfrastructureError, LoadingError

_INSERT_SQL = """
    INSERT INTO supplier_product (
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
        %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
"""


class PostgreSQLSupplierProductLoader:
    """Persist canonical supplier-product data in PostgreSQL."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        pipeline_config: PipelineConfig,
        logger: Logger
    ) -> None:
        self._pool = pool
        self._batch_size = pipeline_config.batch_size
        self._retry_attempts = pipeline_config.retry_attempts
        self._logger = logger

    def load(self, products: pl.DataFrame) -> LoadResult:
        """Atomically persist supplier products."""

        if products.is_empty():
            return LoadResult(records_loaded=0)

        attempts = 0

        while True:
            try:
                return self._load_once(products)
            except InfrastructureError as exc:
                if not exc.retryable or attempts >= self._retry_attempts:
                    raise

                attempts += 1
                self._logger.warning(
                    "Operational supplier product load failed with a "
                    "retryable infrastructure error; retrying "
                    "(attempt %d/%d).",
                    attempts,
                    self._retry_attempts,
                )
            
    def _load_once(self, products: pl.DataFrame) -> LoadResult:
        rows = self._to_rows(products)

        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    for batch in self._batches(rows):
                        cursor.executemany(_INSERT_SQL, batch)

            return LoadResult(records_loaded=len(rows))

        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while loading supplier products.",
                error_code="LOAD_SUPPLIER_PRODUCT_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc

        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected supplier product data.",
                error_code="LOAD_SUPPLIER_PRODUCT_DATABASE_ERROR",
                retryable=False,
            ) from exc

    @staticmethod
    def _to_rows(
        products: pl.DataFrame,
    ) -> list[tuple[object, ...]]:
        """Convert canonical DataFrame rows to database parameters."""

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
        """Yield rows according to the platform batch size."""

        batch_size = self._batch_size

        for start in range(0, len(rows), batch_size):
            yield rows[start : start + batch_size]
