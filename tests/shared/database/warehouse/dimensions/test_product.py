from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from psycopg import DatabaseError, OperationalError
from src.shared.configuration.models import WarehouseConfig
from src.shared.database import (
    PostgreSQLProductDimensionInitializer,
    PostgreSQLProductDimensionRepository,
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
    pool: MagicMock, warehouse_config: WarehouseConfig
) -> PostgreSQLProductDimensionInitializer:
    return PostgreSQLProductDimensionInitializer(
        pool=pool,
        warehouse_config=warehouse_config,
    )


@pytest.fixture
def repository(
    pool: MagicMock,
    warehouse_config: WarehouseConfig,
) -> PostgreSQLProductDimensionRepository:
    return PostgreSQLProductDimensionRepository(
        pool=pool, warehouse_config=warehouse_config
    )


@pytest.fixture
def connection(pool: MagicMock) -> MagicMock:
    return pool.connection.return_value.__enter__.return_value


@pytest.fixture
def cursor(connection: MagicMock) -> MagicMock:
    return connection.cursor.return_value.__enter__.return_value


@pytest.fixture
def effective_from() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


# Tests
def test_upsert_inserts_new_product(
    repository: PostgreSQLProductDimensionRepository,
    cursor: MagicMock,
    effective_from: datetime,
) -> None:
    cursor.fetchone.side_effect = [
        None,
        {"product_key": 101},
    ]

    result = repository.upsert(
        product_id="P001",
        name="Product A",
        description="First version",
        effective_from=effective_from,
    )

    assert result == 101
    assert cursor.execute.call_count == 2

    select_sql = cursor.execute.call_args_list[0].args[0]
    insert_sql = cursor.execute.call_args_list[1].args[0]

    assert "FOR UPDATE" in str(select_sql)
    assert "INSERT INTO" in str(insert_sql)
    assert "dim_product" in str(insert_sql)


def test_upsert_is_idempotent_when_product_is_unchanged(
    repository: PostgreSQLProductDimensionRepository,
    cursor: MagicMock,
    effective_from: datetime,
) -> None:
    cursor.fetchone.return_value = {
        "product_key": 101,
        "name": "Product A",
        "description": "First version",
        "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
    }

    result = repository.upsert(
        product_id="P001",
        name="Product A",
        description="First version",
        effective_from=effective_from,
    )

    assert result == 101
    assert cursor.execute.call_count == 1


def test_upsert_creates_new_version_when_product_changes(
    repository: PostgreSQLProductDimensionRepository, cursor: MagicMock
) -> None:

    second_effective_from = datetime(2026, 2, 1, tzinfo=UTC)

    cursor.fetchone.side_effect = [
        {
            "product_key": 101,
            "name": "Product A",
            "description": "First version",
            "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {"product_key": 102},
    ]

    result = repository.upsert(
        product_id="P001",
        name="Product A",
        description="Updated version",
        effective_from=second_effective_from,
    )

    assert result == 102
    assert cursor.execute.call_count == 3

    select_sql = cursor.execute.call_args_list[0].args[0]
    update_sql = cursor.execute.call_args_list[1].args[0]
    insert_sql = cursor.execute.call_args_list[2].args[0]

    assert "FOR UPDATE" in str(select_sql)
    assert "UPDATE" in str(update_sql)
    assert "is_current = FALSE" in str(update_sql)
    assert "INSERT INTO" in str(insert_sql)


def test_upsert_can_create_multiple_historical_versions(
    repository: PostgreSQLProductDimensionRepository,
    cursor: MagicMock,
) -> None:
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 2, 1, tzinfo=UTC)
    t3 = datetime(2026, 3, 1, tzinfo=UTC)

    cursor.fetchone.side_effect = [
        None,
        {"product_key": 101},
        {
            "product_key": 101,
            "name": "Product A",
            "description": "Version 1",
            "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {"product_key": 102},
        {
            "product_key": 102,
            "name": "Product A",
            "description": "Version 2",
            "valid_from": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {"product_key": 103},
    ]

    assert (
        repository.upsert(
            product_id="P001",
            name="Product A",
            description="Version 1",
            effective_from=t1,
        )
        == 101
    )

    assert (
        repository.upsert(
            product_id="P001",
            name="Product A",
            description="Version 2",
            effective_from=t2,
        )
        == 102
    )

    assert (
        repository.upsert(
            product_id="P001",
            name="Product A",
            description="Version 3",
            effective_from=t3,
        )
        == 103
    )

    assert cursor.execute.call_count == 8


def test_upsert_handles_infrastructure_failure(
    repository: PostgreSQLProductDimensionRepository,
    pool: MagicMock,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    connection.cursor.side_effect = OperationalError("database unavailable")

    with pytest.raises(InfrastructureError) as exc_info:
        repository.upsert(
            product_id="P001",
            name="Product A",
            description=None,
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        )

    assert exc_info.value.retryable is True
    assert exc_info.value.error_code == (
        "WAREHOUSE_PRODUCT_DIMENSION_DATABASE_UNAVAILABLE"
    )


def test_upsert_handles_database_failure(
    repository: PostgreSQLProductDimensionRepository,
    cursor: MagicMock,
) -> None:
    cursor.execute.side_effect = DatabaseError("database rejected operation")

    with pytest.raises(LoadingError) as exc_info:
        repository.upsert(
            product_id="P001",
            name="Product A",
            description=None,
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        )

    assert exc_info.value.retryable is False
    assert exc_info.value.error_code == ("WAREHOUSE_PRODUCT_DIMENSION_UPDATE_FAILED")


def test_upsert_uses_transaction_context(
    repository: PostgreSQLProductDimensionRepository,
    pool: MagicMock,
    cursor: MagicMock,
) -> None:
    cursor.fetchone.side_effect = [
        None,
        {"product_key": 101},
    ]

    repository.upsert(
        product_id="P001",
        name="Product A",
        description=None,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )

    connection_context = pool.connection.return_value
    cursor_context = connection_context.__enter__.return_value.cursor.return_value

    connection_context.__exit__.assert_called_once()
    cursor_context.__exit__.assert_called_once()
