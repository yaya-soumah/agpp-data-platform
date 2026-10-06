from datetime import date
from unittest.mock import MagicMock

import pytest
from psycopg import DatabaseError, OperationalError
from src.shared.configuration.models import WarehouseConfig
from src.shared.database.warehouse.dimensions import (
    PostgreSQLDateDimensionInitializer,
    PostgreSQLDateDimensionRepository,
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
) -> PostgreSQLDateDimensionInitializer:
    return PostgreSQLDateDimensionInitializer(
        pool=pool,
        warehouse_config=warehouse_config,
    )


@pytest.fixture
def repository(
    pool: MagicMock,
    warehouse_config: WarehouseConfig,
) -> PostgreSQLDateDimensionRepository:
    return PostgreSQLDateDimensionRepository(
        pool=pool,
        warehouse_config=warehouse_config,
    )


def test_initialize_creates_table(
    initializer: PostgreSQLDateDimensionInitializer,
    pool: MagicMock,
) -> None:
    initializer.initialize()

    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    cursor.execute.assert_called_once()

    table_sql = cursor.execute.call_args.args[0]

    assert "CREATE TABLE IF NOT EXISTS" in str(table_sql)
    assert "dim_date" in str(table_sql)
    assert "date_key INTEGER PRIMARY KEY" in str(table_sql)
    assert "calendar_date DATE NOT NULL UNIQUE" in str(table_sql)
    assert "year INTEGER NOT NULL" in str(table_sql)
    assert "quarter INTEGER NOT NULL" in str(table_sql)
    assert "month INTEGER NOT NULL" in str(table_sql)
    assert "day_of_week INTEGER NOT NULL" in str(table_sql)
    assert "is_weekend BOOLEAN NOT NULL" in str(table_sql)


def test_initialize_handles_infrastructure_failure(
    initializer: PostgreSQLDateDimensionInitializer,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    connection.cursor.side_effect = OperationalError("database unavailable")

    with pytest.raises(InfrastructureError) as exc_info:
        initializer.initialize()

    assert exc_info.value.retryable is True
    assert exc_info.value.error_code == "DATE_DIMENSION_DATABASE_UNAVAILABLE"


def test_initialize_handles_database_failure(
    initializer: PostgreSQLDateDimensionInitializer,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = DatabaseError("table creation failed")

    with pytest.raises(LoadingError) as exc_info:
        initializer.initialize()

    assert exc_info.value.retryable is False
    assert exc_info.value.error_code == "DATE_DIMENSION_INITIALIZATION_FAILED"


def test_initialize_uses_transaction_context(
    initializer: PostgreSQLDateDimensionInitializer,
    pool: MagicMock,
) -> None:
    initializer.initialize()

    connection_context = pool.connection.return_value
    connection = connection_context.__enter__.return_value
    cursor_context = connection.cursor.return_value

    connection_context.__exit__.assert_called_once()
    cursor_context.__exit__.assert_called_once()


def test_insert_calculates_date_key_and_calendar_attributes(
    repository: PostgreSQLDateDimensionRepository,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    calendar_date = date(2026, 10, 6)

    result = repository.insert(calendar_date)

    assert result == 20261006

    cursor.execute.assert_called_once()

    insert_sql, parameters = cursor.execute.call_args.args

    assert "INSERT INTO" in str(insert_sql)
    assert "dim_date" in str(insert_sql)
    assert "ON CONFLICT (date_key) DO NOTHING" in str(insert_sql)

    assert parameters == (
        20261006,
        date(2026, 10, 6),
        2026,
        4,
        10,
        "October",
        6,
        2,
        "Tuesday",
        41,
        False,
    )


def test_insert_is_idempotent(
    repository: PostgreSQLDateDimensionRepository,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    calendar_date = date(2026, 10, 6)

    first_result = repository.insert(calendar_date)
    second_result = repository.insert(calendar_date)

    assert first_result == 20261006
    assert second_result == 20261006
    assert cursor.execute.call_count == 2

    first_parameters = cursor.execute.call_args_list[0].args[1]
    second_parameters = cursor.execute.call_args_list[1].args[1]

    assert first_parameters == second_parameters


def test_insert_handles_infrastructure_failure(
    repository: PostgreSQLDateDimensionRepository,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    connection.cursor.side_effect = OperationalError("database unavailable")

    with pytest.raises(InfrastructureError) as exc_info:
        repository.insert(date(2026, 10, 6))

    assert exc_info.value.retryable is True
    assert exc_info.value.error_code == "DATE_DIMENSION_DATABASE_UNAVAILABLE"


def test_insert_handles_database_failure(
    repository: PostgreSQLDateDimensionRepository,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = DatabaseError("insert failed")

    with pytest.raises(LoadingError) as exc_info:
        repository.insert(date(2026, 10, 6))

    assert exc_info.value.retryable is False
    assert exc_info.value.error_code == "DATE_DIMENSION_INSERT_FAILED"


def test_insert_uses_transaction_context(
    repository: PostgreSQLDateDimensionRepository,
    pool: MagicMock,
) -> None:
    connection_context = pool.connection.return_value
    connection = connection_context.__enter__.return_value
    cursor_context = connection.cursor.return_value

    repository.insert(date(2026, 10, 6))

    connection_context.__exit__.assert_called_once()
    cursor_context.__exit__.assert_called_once()
