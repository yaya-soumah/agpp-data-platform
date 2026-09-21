from decimal import Decimal
from unittest.mock import MagicMock

import polars as pl
import pytest
from psycopg import DatabaseError, OperationalError
from src.pipelines.supplier_product.loader import (
    PostgreSQLSupplierProductLoader,
)
from src.shared.configuration.models import PipelineConfig
from src.shared.exceptions import InfrastructureError, LoadingError


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        batch_size=2,
        retry_attempts=3,
    )


@pytest.fixture
def pool() -> MagicMock:
    pool = MagicMock()

    return pool


@pytest.fixture
def loader(
    pool: MagicMock,
    pipeline_config: PipelineConfig,
) -> PostgreSQLSupplierProductLoader:
    return PostgreSQLSupplierProductLoader(
        pool=pool,
        pipeline_config=pipeline_config,
    )


@pytest.fixture
def products() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "supplier_product_id": ["SP-001", "SP-002", "SP-003"],
            "supplier_id": ["SUP-001", "SUP-002", "SUP-003"],
            "supplier_sku": ["SKU-001", "SKU-002", None],
            "name": ["Product 1", "Product 2", "Product 3"],
            "description": ["Description 1", None, "Description 3"],
            "price_amount": ["10.500000", "20.250000", "30.750000"],
            "price_currency": ["USD", "EUR", "GBP"],
            "minimum_order_quantity": ["5.000000", "10.000000", "15.000000"],
            "lead_time_days": [5, 10, 15],
        }
    ).with_columns(
        pl.col("price_amount").cast(pl.Decimal(38, 6)),
        pl.col("minimum_order_quantity").cast(pl.Decimal(38, 6)),
    )


def test_load_empty_dataframe_returns_zero(
    loader: PostgreSQLSupplierProductLoader,
    pool: MagicMock,
) -> None:
    products = pl.DataFrame(
        {
            "supplier_product_id": pl.Series([], dtype=pl.String),
            "supplier_id": pl.Series([], dtype=pl.String),
            "supplier_sku": pl.Series([], dtype=pl.String),
            "name": pl.Series([], dtype=pl.String),
            "description": pl.Series([], dtype=pl.String),
            "price_amount": pl.Series([], dtype=pl.Decimal(38, 6)),
            "price_currency": pl.Series([], dtype=pl.String),
            "minimum_order_quantity": pl.Series(
                [],
                dtype=pl.Decimal(38, 6),
            ),
            "lead_time_days": pl.Series([], dtype=pl.Int64),
        }
    )

    result = loader.load(products)

    assert result.records_loaded == 0
    pool.connection.assert_not_called()


def test_load_inserts_rows(
    loader: PostgreSQLSupplierProductLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value

    result = loader.load(products)

    assert result.records_loaded == 3
    assert cursor.executemany.call_count == 2

    first_batch = cursor.executemany.call_args_list[0].args[1]
    second_batch = cursor.executemany.call_args_list[1].args[1]

    assert len(first_batch) == 2
    assert len(second_batch) == 1

    assert first_batch[0] == (
        "SP-001",
        "SUP-001",
        "SKU-001",
        "Product 1",
        "Description 1",
        Decimal("10.500000"),
        "USD",
        Decimal("5.000000"),
        5,
    )

    assert second_batch[0] == (
        "SP-003",
        "SUP-003",
        None,
        "Product 3",
        "Description 3",
        Decimal("30.750000"),
        "GBP",
        Decimal("15.000000"),
        15,
    )


def test_load_uses_pipeline_batch_size(
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    pipeline_config = PipelineConfig(
        batch_size=1,
        retry_attempts=3,
    )

    loader = PostgreSQLSupplierProductLoader(
        pool=pool,
        pipeline_config=pipeline_config,
    )

    loader.load(products)

    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value

    assert cursor.executemany.call_count == 3


def test_load_translates_operational_error(
    loader: PostgreSQLSupplierProductLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.executemany.side_effect = OperationalError("connection failed")

    with pytest.raises(
        InfrastructureError,
        match="PostgreSQL infrastructure failure",
    ) as exc_info:
        loader.load(products)

    assert exc_info.value.retryable is True


def test_load_translates_database_error(
    loader: PostgreSQLSupplierProductLoader,
    pool: MagicMock,
    products: pl.DataFrame,
) -> None:
    cursor = pool.connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.executemany.side_effect = DatabaseError("constraint violation")

    with pytest.raises(
        LoadingError,
        match="PostgreSQL rejected supplier product data",
    ) as exc_info:
        loader.load(products)

    assert exc_info.value.retryable is False


def test_load_failure_rolls_back_transaction(
    loader: PostgreSQLSupplierProductLoader,
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
