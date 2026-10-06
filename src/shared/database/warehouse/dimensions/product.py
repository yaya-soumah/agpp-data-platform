from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Connection, DatabaseError, OperationalError, sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from src.shared.configuration.models import WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError, ValidationError


@dataclass(frozen=True)
class _CurrentProduct:
    product_key: int
    name: str
    description: str | None
    valid_from: datetime


class PostgreSQLProductDimensionInitializer:
    """Initializes the PostgreSQL product dimension."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def initialize(self) -> None:
        """Create the product dimension if it does not exist."""
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(self._create_table_sql())
                    cursor.execute(self._create_current_product_index_sql())
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while initializing "
                "the product dimension.",
                error_code="PRODUCT_DIMENSION_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the product dimension initialization.",
                error_code="PRODUCT_DIMENSION_INITIALIZATION_FAILED",
                retryable=False,
            ) from exc

    def _create_table_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {}.dim_product (
                product_key BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY,
                product_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                valid_from TIMESTAMPTZ NOT NULL,
                valid_to TIMESTAMPTZ,
                is_current BOOLEAN NOT NULL,

                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,

                CONSTRAINT ck_dim_product_valid_period
                    CHECK (
                        valid_to IS NULL
                        OR valid_from < valid_to
                    ),

                CONSTRAINT ck_dim_product_current_state
                    CHECK (
                        (
                            is_current = TRUE
                            AND valid_to IS NULL
                        )
                        OR
                        (
                            is_current = FALSE
                            AND valid_to IS NOT NULL
                        )
                    )
            )
            """
        ).format(sql.Identifier(self._warehouse_config.warehouse_schema))

    def _create_current_product_index_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_dim_product_current
            ON {}.dim_product (product_id)
            WHERE is_current = TRUE
            """
        ).format(sql.Identifier(self._warehouse_config.warehouse_schema))


class PostgreSQLProductDimensionRepository:
    """Maintains the product dimension using SCD Type 2 semantics."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def upsert(
        self,
        product_id: str,
        name: str,
        description: str | None,
        effective_from: datetime,
    ) -> int:
        """Insert or version a canonical product and return its warehouse key."""

        try:
            with self._pool.connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    current = self._get_current_product(
                        cursor=cursor,
                        product_id=product_id,
                    )
                    if current is None:
                        return self._insert_current_product(
                            cursor=cursor,
                            product_id=product_id,
                            name=name,
                            description=description,
                            effective_from=effective_from,
                        )

                    if self._is_unchanged(
                        current=current,
                        name=name,
                        description=description,
                    ):
                        return current.product_key

                    if effective_from < current.valid_from:
                        raise ValidationError(
                            "Product effective timestamp cannot precede "
                            "the current product version.",
                            error_code="WAREHOUSE_PRODUCT_DIMENSION_EFFECTIVE_DATE_OUT_OF_ORDER",
                        )

                    self._close_current_product(
                        cursor=cursor,
                        product_key=current.product_key,
                        effective_to=effective_from,
                    )
                    return self._insert_current_product(
                        cursor=cursor,
                        product_id=product_id,
                        name=name,
                        description=description,
                        effective_from=effective_from,
                    )
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while updating "
                "the product dimension.",
                error_code="WAREHOUSE_PRODUCT_DIMENSION_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the product dimension update.",
                error_code="WAREHOUSE_PRODUCT_DIMENSION_UPDATE_FAILED",
                retryable=False,
            ) from exc

    def _get_current_product(
        self,
        cursor: Any,
        product_id: str,
    ) -> _CurrentProduct | None:
        cursor.execute(
            sql.SQL(
                """
                SELECT
                    product_key,
                    name,
                    description,
                    valid_from
                FROM {}.dim_product
                WHERE product_id = %s AND is_current = True
                FOR UPDATE
                """
            ).format(
                sql.Identifier(self._warehouse_config.warehouse_schema),
            ),
            (product_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _CurrentProduct(
            product_key=row["product_key"],
            name=row["name"],
            description=row["description"],
            valid_from=row["valid_from"],
        )

    @staticmethod
    def _is_unchanged(
        current: _CurrentProduct,
        name: str,
        description: str | None,
    ) -> bool:
        return current.name == name and current.description == description

    def _close_current_product(
        self,
        cursor: Any,
        product_key: int,
        effective_to: datetime,
    ) -> None:
        cursor.execute(
            sql.SQL(
                """
                UPDATE {}.dim_product
                SET
                    valid_to = %s,
                    is_current = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_key = %s
                """
            ).format(sql.Identifier(self._warehouse_config.warehouse_schema)),
            (effective_to, product_key),
        )

    def _insert_current_product(
        self,
        cursor: Any,
        product_id: str,
        name: str,
        description: str | None,
        effective_from: datetime,
    ) -> int:
        cursor.execute(
            sql.SQL(
                """
                INSERT INTO {}.dim_product (
                    product_id,
                    name,
                    description,
                    valid_from,
                    valid_to,
                    is_current,
                    created_at,
                    updated_at
                )
                VALUES (
                %s,
                %s,
                %s,
                %s,
                NULL,
                TRUE,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
                )
                RETURNING product_key
                """
            ).format(sql.Identifier(self._warehouse_config.warehouse_schema)),
            (
                product_id,
                name,
                description,
                effective_from,
            ),
        )
        result = cursor.fetchone()

        if result is None:
            raise LoadingError(
                "PostgreSQL did not return the generated product_key",
                error_code="WAREHOUSE_PRODUCT_DIMENSION_KEY_NOT_RETURNED",
            )
        return int(result["product_key"])
