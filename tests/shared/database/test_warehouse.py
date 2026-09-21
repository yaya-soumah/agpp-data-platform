from unittest.mock import MagicMock

import pytest
from psycopg import DatabaseError, OperationalError
from src.shared.configuration.models import WarehouseConfig
from src.shared.database import (
    PostgreSQLWarehouseSchemaInitializer,
)
from src.shared.exceptions import InfrastructureError, LoadingError


@pytest.fixture
def warehouse_config() -> WarehouseConfig:
    return WarehouseConfig(schema="analytics")


@pytest.fixture
def pool() -> MagicMock:
    return MagicMock()


@pytest.fixture
def initializer(
    pool: MagicMock,
    warehouse_config: WarehouseConfig,
) -> PostgreSQLWarehouseSchemaInitializer:
    return PostgreSQLWarehouseSchemaInitializer(
        pool=pool,
        warehouse_config=warehouse_config,
    )


def test_initialize_creates_schema_and_table(
    initializer: PostgreSQLWarehouseSchemaInitializer,
    pool: MagicMock,
) -> None:
    initializer.initialize()

    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    assert cursor.execute.call_count == 2

    schema_sql = cursor.execute.call_args_list[0].args[0]
    table_sql = cursor.execute.call_args_list[1].args[0]

    assert "CREATE SCHEMA IF NOT EXISTS" in str(schema_sql)
    assert "CREATE TABLE IF NOT EXISTS" in str(table_sql)
    assert "supplier_product" in str(table_sql)
    assert "analytics" in str(table_sql)


def test_initialize_handles_infrastructure_failure(
    initializer: PostgreSQLWarehouseSchemaInitializer,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    connection.cursor.side_effect = OperationalError("database unavailable")

    with pytest.raises(InfrastructureError) as exc_info:
        initializer.initialize()

    assert exc_info.value.retryable is True
    assert exc_info.value.error_code == ("WAREHOUSE_SCHEMA_DATABASE_UNAVAILABLE")


def test_initialize_handles_database_failure(
    initializer: PostgreSQLWarehouseSchemaInitializer,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = DatabaseError("schema creation failed")

    with pytest.raises(LoadingError) as exc_info:
        initializer.initialize()

    assert exc_info.value.retryable is False
    assert exc_info.value.error_code == ("WAREHOUSE_SCHEMA_INITIALIZATION_FAILED")


def test_initialize_uses_transaction_context(
    initializer: PostgreSQLWarehouseSchemaInitializer,
    pool: MagicMock,
) -> None:
    initializer.initialize()

    connection_context = pool.connection.return_value
    connection = connection_context.__enter__.return_value

    cursor_context = connection.cursor.return_value

    connection_context.__exit__.assert_called_once()
    cursor_context.__exit__.assert_called_once()
