from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aioftp
import polars as pl
import pytest
from src.pipelines.supplier_product.config import (
    FTPSourceConfig,
    SupplierProductSourceType,
)
from src.pipelines.supplier_product.extractors.ftp import FTPExtractor
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
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.exceptions import ConfigurationError, DataExtractionError


@pytest.fixture
def ftp_config() -> FTPSourceConfig:
    return FTPSourceConfig(
        name="supplier_products_ftp",
        type=SupplierProductSourceType.FTP,
        host="ftp.supplier.example.com",
        port=21,
        username="supplier_user",
        password_env_var="SUPPLIER_FTP_PASSWORD",
        path=Path("supplier_products.csv"),
    )


@pytest.fixture
def runtime_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> RuntimeEnvironment:
    monkeypatch.setenv("SUPPLIER_FTP_PASSWORD", "secret-password")
    return RuntimeEnvironment()


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


@pytest.fixture
def logger() -> Mock:
    return Mock()


@pytest.mark.asyncio
async def test_extract_returns_dataframe(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    runtime_environment: RuntimeEnvironment,
    logger: Mock,
) -> None:
    dataframe = pl.DataFrame(
        {
            "supplier_id": ["S001"],
            "product_id": ["P001"],
            "price": [100.50],
        }
    )

    client = AsyncMock()
    client.download = AsyncMock()

    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "src.pipelines.supplier_product.extractors.ftp.aioftp.Client.context",
            return_value=async_context,
        ),
        patch(
            "src.pipelines.supplier_product.extractors.ftp.pl.read_csv",
            return_value=dataframe,
        ) as read_csv,
    ):
        extractor = FTPExtractor(
            app_config=app_config,
            source_config=ftp_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )

        result = await extractor.extract()

    assert result.equals(dataframe)
    read_csv.assert_called_once()


@pytest.mark.asyncio
async def test_extract_connects_using_configured_credentials(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    runtime_environment: RuntimeEnvironment,
    logger: Mock,
) -> None:
    client = AsyncMock()

    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "src.pipelines.supplier_product.extractors.ftp.aioftp.Client.context",
            return_value=async_context,
        ) as ftp_context,
        patch(
            "src.pipelines.supplier_product.extractors.ftp.pl.read_csv",
            return_value=pl.DataFrame(),
        ),
    ):
        extractor = FTPExtractor(
            app_config=app_config,
            source_config=ftp_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )

        await extractor.extract()

    ftp_context.assert_called_once_with(
        "ftp.supplier.example.com",
        port=21,
        user="supplier_user",
        password="secret-password",
    )


@pytest.mark.asyncio
async def test_extract_downloads_configured_file(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    runtime_environment: RuntimeEnvironment,
    logger: Mock,
) -> None:
    client = AsyncMock()

    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "src.pipelines.supplier_product.extractors.ftp.aioftp.Client.context",
            return_value=async_context,
        ),
        patch(
            "src.pipelines.supplier_product.extractors.ftp.pl.read_csv",
            return_value=pl.DataFrame(),
        ),
    ):
        extractor = FTPExtractor(
            app_config=app_config,
            source_config=ftp_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )

        await extractor.extract()

    client.download.assert_awaited_once()

    remote_path, local_path = client.download.await_args.args

    assert remote_path == "supplier_products.csv"
    assert isinstance(local_path, str)
    assert Path(local_path).name == "supplier_products.csv"


@pytest.mark.asyncio
async def test_extract_raises_configuration_error_when_password_is_missing(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    logger: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPPLIER_FTP_PASSWORD", raising=False)

    runtime_environment = RuntimeEnvironment()
    extractor = FTPExtractor(
        app_config=app_config,
        source_config=ftp_config,
        runtime_environment=runtime_environment,
        logger=logger,
    )

    with pytest.raises(ConfigurationError) as exc_info:
        await extractor.extract()

    assert exc_info.value.error_code == "CONFIG_RUNTIME_VARIABLE_NOT_SET"


@pytest.mark.asyncio
async def test_extract_retries_retryable_ftp_error(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    runtime_environment: RuntimeEnvironment,
    logger: Mock,
) -> None:
    origin = aioftp.StatusCodeError(
        "550", "File unavailable", info="550 File unavailable"
    )

    client = AsyncMock()
    client.download = AsyncMock(side_effect=origin)

    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "src.pipelines.supplier_product.extractors.ftp.aioftp.Client.context",
        return_value=async_context,
    ):
        extractor = FTPExtractor(
            app_config=app_config,
            source_config=ftp_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )

        with pytest.raises(DataExtractionError) as exc_info:
            await extractor.extract()

    assert client.download.await_count == app_config.pipeline.retry_attempts + 1
    assert exc_info.value.error_code == "EXTRACT_FTP_FAILED"
    assert exc_info.value.retryable is True
    assert exc_info.value.__cause__ is origin
    assert exc_info.value.context["host"] == "ftp.supplier.example.com"
    assert exc_info.value.context["path"] == "supplier_products.csv"


@pytest.mark.asyncio
async def test_extract_does_not_retry_file_processing_error(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    runtime_environment: RuntimeEnvironment,
    logger: Mock,
) -> None:
    origin = ValueError("Invalid CSV data")

    client = AsyncMock()

    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "src.pipelines.supplier_product.extractors.ftp.aioftp.Client.context",
            return_value=async_context,
        ),
        patch(
            "src.pipelines.supplier_product.extractors.ftp.pl.read_csv",
            side_effect=origin,
        ),
    ):
        extractor = FTPExtractor(
            app_config=app_config,
            source_config=ftp_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )

        with pytest.raises(DataExtractionError) as exc_info:
            await extractor.extract()

    assert client.download.await_count == 1
    assert exc_info.value.error_code == "EXTRACT_FTP_FAILED"
    assert exc_info.value.retryable is False
    assert exc_info.value.__cause__ is origin


@pytest.mark.asyncio
async def test_extract_does_not_expose_password_in_extraction_error(
    app_config: AppConfig,
    ftp_config: FTPSourceConfig,
    runtime_environment: RuntimeEnvironment,
    logger: Mock,
) -> None:
    client = AsyncMock()
    origin = aioftp.AIOFTPException("FTP connection failed")
    client.download.side_effect = origin

    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "src.pipelines.supplier_product.extractors.ftp.aioftp.Client.context",
        return_value=async_context,
    ):
        extractor = FTPExtractor(
            app_config=app_config,
            source_config=ftp_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )

        with pytest.raises(DataExtractionError) as exc_info:
            await extractor.extract()

    error = exc_info.value

    assert "secret-password" not in str(error)
    assert "secret-password" not in repr(error)
    assert "secret-password" not in str(error.context)

    for call in logger.error.call_args_list:
        assert "secret-password" not in str(call)
