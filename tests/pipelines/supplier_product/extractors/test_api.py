from logging import Logger
from unittest.mock import AsyncMock, Mock, patch

import httpx
import polars as pl
import pytest
from src.pipelines.supplier_product.config import (
    APISourceConfig,
    SupplierProductSourceType,
)
from src.pipelines.supplier_product.extractors import APIExtractor
from src.shared.configuration.models import (
    AppConfig,
    ApplicationConfig,
    DatabaseConfig,
    Environment,
    EnvironmentConfig,
    FeaturesConfig,
    PathsConfig,
    PipelineConfig,
    WarehouseConfig,
)
from src.shared.exceptions import DataExtractionError


@pytest.fixture
def logger() -> Mock:
    return Mock()


@pytest.fixture
def source_config() -> APISourceConfig:
    return APISourceConfig(
        name="supplier_products",
        type=SupplierProductSourceType.API,
        url="https://example.com/api",
    )


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig(
        application=ApplicationConfig(
            name="AGPP Data Platform",
            version="0.1.0",
        ),
        environment_name=Environment.DEVELOPMENT,
        environment=EnvironmentConfig(timezone="UTC"),
        pipeline=PipelineConfig(
            batch_size=1000,
            retry_attempts=3,
        ),
        warehouse=WarehouseConfig(schema="analytics"),
        database=DatabaseConfig(
            port=5432,
            pool_size=10,
            connection_timeout=30,
        ),
        paths=PathsConfig(
            raw_data="data/raw",
            processed_data="data/processed",
            archive_data="data/archive",
        ),
        features=FeaturesConfig(
            enable_metrics=False,
            enable_profiling=False,
        ),
    )


@pytest.mark.asyncio
async def test_extract_returns_dataFrames(
    app_config: AppConfig, source_config: APISourceConfig, logger: Logger
) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [
        {"supplier_id": "S001", "product_id": "P001"},
        {"supplier_id": "S002", "product_id": "P002"},
    ]

    with patch(
        "src.pipelines.supplier_product.extractors.api.httpx.AsyncClient"
    ) as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.get = AsyncMock(return_value=response)

        extractor = APIExtractor(
            app_config=app_config,
            source_config=source_config,
            logger=logger,
        )

        result = await extractor.extract()

    assert isinstance(result, pl.DataFrame)
    assert result.height == 2
    assert result.columns == ["supplier_id", "product_id"]


@pytest.mark.asyncio
async def test_extract_retries_retryable_error(
    app_config: AppConfig,
    source_config: APISourceConfig,
    logger: Mock,
) -> None:
    origin = httpx.ConnectError("connection failed")

    with patch(
        "src.pipelines.supplier_product.extractors.api.httpx.AsyncClient"
    ) as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.get = AsyncMock(side_effect=origin)

        extractor = APIExtractor(
            app_config=app_config,
            source_config=source_config,
            logger=logger,
        )

        with pytest.raises(DataExtractionError) as exc_info:
            await extractor.extract()

    assert client.get.await_count == app_config.pipeline.retry_attempts + 1
    assert exc_info.value.retryable is True
    assert exc_info.value.__cause__ is origin


@pytest.mark.asyncio
async def test_extract_does_not_retry_client_error(
    app_config: AppConfig, source_config: APISourceConfig, logger: Mock
) -> None:
    response = Mock()
    response.status_code = 404

    error = httpx.HTTPStatusError("Not found", request=Mock(), response=response)

    response.raise_for_status.side_effect = error

    with patch(
        "src.pipelines.supplier_product.extractors.api.httpx.AsyncClient"
    ) as client_class:
        client = client_class.return_value.__aenter__.return_value
        client.get = AsyncMock(return_value=response)

        extractor = APIExtractor(
            app_config=app_config,
            source_config=source_config,
            logger=logger,
        )

        with pytest.raises(DataExtractionError) as exc_info:
            await extractor.extract()

    assert client.get.await_count == 1
    assert exc_info.value.retryable is False
    assert exc_info.value.__cause__ is error
