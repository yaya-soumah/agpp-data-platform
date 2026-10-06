from datetime import date

from psycopg import Connection, DatabaseError, OperationalError, sql
from psycopg_pool import ConnectionPool
from src.shared.configuration.models import WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError


class PostgreSQLDateDimensionInitializer:
    """Initializes the PostgreSQL date dimension."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def initialize(self) -> None:
        """Create the date dimension if it does not exist."""
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(self._create_table_sql())
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while initializing "
                "the date dimension.",
                error_code="DATE_DIMENSION_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the date dimension initialization.",
                error_code="DATE_DIMENSION_INITIALIZATION_FAILED",
                retryable=False,
            ) from exc

    def _create_table_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {}.dim_date (
                date_key INTEGER PRIMARY KEY,
                calendar_date DATE NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                month INTEGER NOT NULL,
                month_name TEXT NOT NULL,
                day_of_month INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                day_name TEXT NOT NULL,
                week_of_year INTEGER NOT NULL,
                is_weekend BOOLEAN NOT NULL,

                CONSTRAINT ck_dim_date_key
                    CHECK (
                        date_key =
                        (
                            EXTRACT(
                                YEAR FROM calendar_date
                            )::INTEGER * 10000
                            +
                            EXTRACT(
                                MONTH FROM calendar_date
                            )::INTEGER * 100
                            +
                            EXTRACT(
                                DAY FROM calendar_date
                            )::INTEGER
                        )
                    ),

                CONSTRAINT ck_dim_date_quarter
                    CHECK (quarter BETWEEN 1 AND 4),

                CONSTRAINT ck_dim_date_month
                    CHECK (month BETWEEN 1 AND 12),

                CONSTRAINT ck_dim_date_day_of_month
                    CHECK (day_of_month BETWEEN 1 AND 31),

                CONSTRAINT ck_dim_date_day_of_week
                    CHECK (day_of_week BETWEEN 1 AND 7),

                CONSTRAINT ck_dim_date_week_of_year
                    CHECK (week_of_year BETWEEN 1 AND 53)
            )
            """
        ).format(sql.Identifier(self._warehouse_config.warehouse_schema))


class PostgreSQLDateDimensionRepository:
    """Provides access to the static date dimension."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def insert(self, calendar_date: date) -> int:
        """Insert a calendar date and return its date key."""
        date_key = (
            calendar_date.year * 10000 + calendar_date.month * 100 + calendar_date.day
        )

        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL(
                            """
                            INSERT INTO {}.dim_date (
                                date_key,
                                calendar_date,
                                year,
                                quarter,
                                month,
                                month_name,
                                day_of_month,
                                day_of_week,
                                day_name,
                                week_of_year,
                                is_weekend
                            )
                            VALUES (
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s
                            )
                            ON CONFLICT (date_key) DO NOTHING
                            """
                        ).format(
                            sql.Identifier(self._warehouse_config.warehouse_schema)
                        ),
                        (
                            date_key,
                            calendar_date,
                            calendar_date.year,
                            (calendar_date.month - 1) // 3 + 1,
                            calendar_date.month,
                            calendar_date.strftime("%B"),
                            calendar_date.day,
                            calendar_date.isoweekday(),
                            calendar_date.strftime("%A"),
                            calendar_date.isocalendar().week,
                            calendar_date.isoweekday() >= 6,
                        ),
                    )

            return date_key

        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while inserting the date dimension.",
                error_code="DATE_DIMENSION_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the date dimension insert.",
                error_code="DATE_DIMENSION_INSERT_FAILED",
                retryable=False,
            ) from exc
