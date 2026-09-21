from unittest.mock import MagicMock

import polars as pl
import pytest
from psycopg import DatabaseError, OperationalError
from src.pipelines.supplier_product.loader import (
    PostgreSQLSupplierProductWarehouseLoader,
    WarehouseLoadResult,
)
from src.shared.configuration.models import PipelineConfig, WarehouseConfig
from src.shared.exceptions import InfrastructureError, LoadingError


@pytest.fixture
def pool() -> MagicMock:
    return MagicMock()


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        batch_size=2,
        retry_attempts=3,
    )


@pytest.fixture
def warehouse_config() -> WarehouseConfig:
    return WarehouseConfig(schema="analytics")


@pytest.fixture
def loader(
    pool: MagicMock,
    pipeline_config: PipelineConfig,
    warehouse_config: WarehouseConfig,
) -> PostgreSQLSupplierProductWarehouseLoader:
    return PostgreSQLSupplierProductWarehouseLoader(
        pool=pool,
        pipeline_config=pipeline_config,
        warehouse_config=warehouse_config,
    )


@pytest.fixture
def products() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-002", "SP-003"],
            "supplier_id": ["SUP-001", "SUP-001", "SUP-002"],
            "supplier_sku": ["SKU-001", "SKU-002", None],
            "name": ["Product A", "Product B", "Product C"],
            "description": ["Desc A", "Desc B", None],
            "price_amount": [10.5, 20.0, 30.25],
            "price_currency": ["USD", "EUR", "CNY"],
            "minimum_order_quantity": [1, 5, 10],
            "lead_time_days": [3, 5, 7],
        }
    )


def test_load_empty_dataframe_returns_zero_without_database_access(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
) -> None:
    products = pl.DataFrame(
        {
            "supplier_product_id": pl.Series([], dtype=pl.String),
            "supplier_id": pl.Series([], dtype=pl.String),
            "supplier_sku": pl.Series([], dtype=pl.String),
            "name": pl.Series([], dtype=pl.String),
            "description": pl.Series([], dtype=pl.String),
            "price_amount": pl.Series([], dtype=pl.Float64),
            "price_currency": pl.Series([], dtype=pl.String),
            "minimum_order_quantity": pl.Series([], dtype=pl.Float64),
            "lead_time_days": pl.Series([], dtype=pl.Int64),
        }
    )

    result = loader.load(products)

    assert result == WarehouseLoadResult(records_loaded=0)
    pool.connection.assert_not_called()


def test_load_returns_number_of_records_loaded(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    products: pl.DataFrame,
) -> None:
    result = loader.load(products)

    assert result == WarehouseLoadResult(records_loaded=3)


def test_load_uses_configured_batch_size(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    loader.load(products)

    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    assert cursor.executemany.call_count == 2


def test_load_maps_canonical_columns_in_expected_order(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    loader.load(products)

    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    first_batch = cursor.executemany.call_args_list[0].args[1]

    assert first_batch == [
        (
            "SP-001",
            "SUP-001",
            "SKU-001",
            "Product A",
            "Desc A",
            10.5,
            "USD",
            1,
            3,
        ),
        (
            "SP-002",
            "SUP-001",
            "SKU-002",
            "Product B",
            "Desc B",
            20.0,
            "EUR",
            5,
            5,
        ),
    ]


def test_load_places_remaining_records_in_final_batch(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    loader.load(products)

    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    second_batch = cursor.executemany.call_args_list[1].args[1]

    assert second_batch == [
        (
            "SP-003",
            "SUP-002",
            None,
            "Product C",
            None,
            30.25,
            "CNY",
            10,
            7,
        )
    ]


def test_load_uses_configured_warehouse_schema(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    loader.load(products)

    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value

    statement = cursor.executemany.call_args_list[0].args[0]

    assert "analytics" in str(statement)
    assert "supplier_product" in str(statement)


def test_load_handles_infrastructure_failure(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.executemany.side_effect = OperationalError("database unavailable")

    with pytest.raises(InfrastructureError) as exc_info:
        loader.load(products)

    assert exc_info.value.retryable is True
    assert exc_info.value.error_code == ("WAREHOUSE_LOAD_DATABASE_UNAVAILABLE")


def test_load_handles_database_failure(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    connection = pool.connection.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.executemany.side_effect = DatabaseError("insert failed")

    with pytest.raises(LoadingError) as exc_info:
        loader.load(products)

    assert exc_info.value.retryable is False
    assert exc_info.value.error_code == ("WAREHOUSE_LOAD_DATABASE_ERROR")


def test_load_exits_database_contexts_on_failure(
    loader: PostgreSQLSupplierProductWarehouseLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    connection_context = pool.connection.return_value
    connection = connection_context.__enter__.return_value

    cursor_context = connection.cursor.return_value
    cursor = cursor_context.__enter__.return_value

    cursor.executemany.side_effect = DatabaseError("insert failed")

    with pytest.raises(LoadingError):
        loader.load(products)

    cursor_context.__exit__.assert_called_once()
    connection_context.__exit__.assert_called_once()
