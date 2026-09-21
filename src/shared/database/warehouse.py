from psycopg import Connection, DatabaseError, OperationalError, sql
from psycopg_pool import ConnectionPool
from src.shared.configuration.models import WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError

_SUPPLIER_PRODUCT_TABLE = "supplier_product"


class PostgreSQLWarehouseSchemaInitializer:
    """Initializes the PostgreSQL warehouse schema."""

    def __init__(
        self,
        pool: ConnectionPool[Connection],
        warehouse_config: WarehouseConfig,
    ) -> None:
        self._pool = pool
        self._warehouse_config = warehouse_config

    def initialize(self) -> None:
        """Create the warehouse schema and supplier product table if needed."""
        try:
            with self._pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(self._create_schema_sql())
                    cursor.execute(self._create_supplier_product_table_sql())
        except OperationalError as exc:
            raise InfrastructureError(
                "PostgreSQL infrastructure failure while initializing "
                "the warehouse schema.",
                error_code="WAREHOUSE_SCHEMA_DATABASE_UNAVAILABLE",
                retryable=True,
            ) from exc
        except DatabaseError as exc:
            raise LoadingError(
                "PostgreSQL rejected the warehouse schema initialization.",
                error_code="WAREHOUSE_SCHEMA_INITIALIZATION_FAILED",
                retryable=False,
            ) from exc

    def _create_schema_sql(self) -> sql.Composed:
        return sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
            sql.Identifier(self._warehouse_config.warehouse_schema)
        )

    def _create_supplier_product_table_sql(self) -> sql.Composed:
        return sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {}.{} (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                supplier_product_id TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                supplier_sku TEXT,
                name TEXT NOT NULL,
                description TEXT,
                price_amount NUMERIC(38, 6),
                price_currency CHAR(3),
                minimum_order_quantity NUMERIC(38, 6),
                lead_time_days INTEGER
            )
            """
        ).format(
            sql.Identifier(self._warehouse_config.warehouse_schema),
            sql.Identifier(_SUPPLIER_PRODUCT_TABLE),
        )
