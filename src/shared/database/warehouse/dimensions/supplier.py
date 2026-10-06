from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Connection, DatabaseError, OperationalError, sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from src.shared.configuration.models import WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError, ValidationError


@dataclass(frozen=True)
class _CurrentSupplier:
    supplier_key: int
    name: str
    valid_from: datetime


class PostgreSQLSupplierDimensionInitializer:
    """Initializes the PostgreSQL supplier dimension."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def initialize(self) -> None:
        """Create the supplier dimension if it does not exist."""
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(self._create_table_sql())
                    cursor.execute(self._create_current_supplier_index_sql())
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while initializing "
                "the supplier dimension.",
                error_code="SUPPLIER_DIMENSION_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the supplier dimension initialization.",
                error_code="SUPPLIER_DIMENSION_INITIALIZATION_FAILED",
                retryable=False,
            ) from exc

    def _create_table_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {}.dim_supplier (
                supplier_key BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY,
                supplier_id TEXT NOT NULL,
                name TEXT NOT NULL,
                valid_from TIMESTAMPTZ NOT NULL,
                valid_to TIMESTAMPTZ,
                is_current BOOLEAN NOT NULL,

                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,

                CONSTRAINT ck_dim_supplier_valid_period
                    CHECK (
                        valid_to IS NULL
                        OR valid_from < valid_to
                    ),

                CONSTRAINT ck_dim_supplier_current_state
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

    def _create_current_supplier_index_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_dim_supplier_current
            ON {}.dim_supplier (supplier_id)
            WHERE is_current = TRUE
            """
        ).format(sql.Identifier(self._warehouse_config.warehouse_schema))


class PostgreSQLSupplierDimensionRepository:
    """Maintains the supplier dimension using SCD Type 2 semantics."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def upsert(
        self,
        supplier_id: str,
        name: str,
        effective_from: datetime,
    ) -> int:
        """Insert or version a canonical supplier and return its warehouse key."""

        try:
            with self._pool.connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    current = self._get_current_supplier(
                        cursor=cursor,
                        supplier_id=supplier_id,
                    )
                    if current is None:
                        return self._insert_current_supplier(
                            cursor=cursor,
                            supplier_id=supplier_id,
                            name=name,
                            effective_from=effective_from,
                        )

                    if self._is_unchanged(
                        current=current,
                        name=name,
                    ):
                        return current.supplier_key

                    if effective_from <= current.valid_from:
                        raise ValidationError(
                            "Supplier effective timestamp cannot precede "
                            "the current supplier version.",
                            error_code="WAREHOUSE_SUPPLIER_DIMENSION_EFFECTIVE_DATE_OUT_OF_ORDER",
                        )

                    self._close_current_supplier(
                        cursor=cursor,
                        supplier_key=current.supplier_key,
                        effective_to=effective_from,
                    )
                    return self._insert_current_supplier(
                        cursor=cursor,
                        supplier_id=supplier_id,
                        name=name,
                        effective_from=effective_from,
                    )
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while updating "
                "the supplier dimension.",
                error_code="WAREHOUSE_SUPPLIER_DIMENSION_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the supplier dimension update.",
                error_code="WAREHOUSE_SUPPLIER_DIMENSION_UPDATE_FAILED",
                retryable=False,
            ) from exc

    def _get_current_supplier(
        self,
        cursor: Any,
        supplier_id: str,
    ) -> _CurrentSupplier | None:
        cursor.execute(
            sql.SQL(
                """
                SELECT
                    supplier_key,
                    name,
                    valid_from
                FROM {}.dim_supplier
                WHERE supplier_id = %s AND is_current = True
                FOR UPDATE
                """
            ).format(
                sql.Identifier(self._warehouse_config.warehouse_schema),
            ),
            (supplier_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _CurrentSupplier(
            supplier_key=row["supplier_key"],
            name=row["name"],
            valid_from=row["valid_from"],
        )

    @staticmethod
    def _is_unchanged(
        current: _CurrentSupplier,
        name: str,
    ) -> bool:
        return current.name == name

    def _close_current_supplier(
        self,
        cursor: Any,
        supplier_key: int,
        effective_to: datetime,
    ) -> None:
        cursor.execute(
            sql.SQL(
                """
                UPDATE {}.dim_supplier
                SET
                    valid_to = %s,
                    is_current = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE supplier_key = %s
                """
            ).format(sql.Identifier(self._warehouse_config.warehouse_schema)),
            (effective_to, supplier_key),
        )

    def _insert_current_supplier(
        self,
        cursor: Any,
        supplier_id: str,
        name: str,
        effective_from: datetime,
    ) -> int:
        cursor.execute(
            sql.SQL(
                """
                INSERT INTO {}.dim_supplier (
                    supplier_id,
                    name,
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
                NULL,
                TRUE,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
                )
                RETURNING supplier_key
                """
            ).format(sql.Identifier(self._warehouse_config.warehouse_schema)),
            (
                supplier_id,
                name,
                effective_from,
            ),
        )
        result = cursor.fetchone()

        if result is None:
            raise LoadingError(
                "PostgreSQL did not return the generated supplier_key",
                error_code="WAREHOUSE_SUPPLIER_DIMENSION_KEY_NOT_RETURNED",
            )
        return int(result["supplier_key"])
