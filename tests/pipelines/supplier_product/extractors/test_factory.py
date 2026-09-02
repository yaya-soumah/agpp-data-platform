from logging import Logger
from pathlib import Path

from src.pipelines.supplier_product.config import (
    APISourceConfig,
    CSVSourceConfig,
    FTPSourceConfig,
)
from src.pipelines.supplier_product.extractors import (
    APIExtractor,
    CSVExtractor,
    FTPExtractor,
    SupplierProductExtractorFactory,
)
from src.shared.configuration.environment import Environment
from src.shared.configuration.models import (
    AppConfig,
    ApplicationConfig,
    ConsoleHandlerConfig,
    DatabaseConfig,
    EnvironmentConfig,
    FeaturesConfig,
    FileHandlerConfig,
    LoggingConfig,
    LoggingEnvironmentLevelConfig,
    LoggingFormatConfig,
    LoggingHandlersConfig,
    PathsConfig,
    PipelineConfig,
    WarehouseConfig,
)
from src.shared.configuration.runtime import RuntimeEnvironment


def create_app_config() -> AppConfig:
    """Create a valid application configuration for testing."""

    return AppConfig(
        application=ApplicationConfig(
            name="AGPP",
            version="1.0.0",
        ),
        environment_name=Environment.TESTING,
        environment=EnvironmentConfig(
            timezone="UTC",
        ),
        pipeline=PipelineConfig(
            batch_size=1000,
            retry_attempts=3,
        ),
        warehouse=WarehouseConfig(
            schema="analytics",
        ),
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


def create_logging_config() -> LoggingConfig:
    """Create a valid logging configuration for testing."""

    return LoggingConfig(
        version=1,
        format=LoggingFormatConfig(
            standard="%(asctime)s %(levelname)s %(name)s %(message)s",
        ),
        handlers=LoggingHandlersConfig(
            console=ConsoleHandlerConfig(enabled=True),
            file=FileHandlerConfig(
                enabled=False,
                path="logs/agpp.log",
            ),
        ),
        development=LoggingEnvironmentLevelConfig(level="DEBUG"),
        testing=LoggingEnvironmentLevelConfig(level="INFO"),
        production=LoggingEnvironmentLevelConfig(level="WARNING"),
    )


def create_factory() -> SupplierProductExtractorFactory:
    """Create an extractor factory with valid shared dependencies."""

    return SupplierProductExtractorFactory(
        app_config=create_app_config(),
        runtime_environment=RuntimeEnvironment(),
        logger=Logger("test"),
    )


def test_create_returns_csv_extractor() -> None:
    """Factory creates a CSV extractor for CSV configuration."""

    source_config = CSVSourceConfig(
        name="supplier_master",
        type="csv",
        path=Path("supplier_master.csv"),
    )

    extractor = create_factory().create(source_config)

    assert isinstance(extractor, CSVExtractor)


def test_create_returns_api_extractor() -> None:
    """Factory creates an API extractor for API configuration."""

    source_config = APISourceConfig(
        name="supplier_products_api",
        type="api",
        url="https://example.com/products",
    )

    extractor = create_factory().create(source_config)

    assert isinstance(extractor, APIExtractor)


def test_create_returns_ftp_extractor() -> None:
    """Factory creates an FTP extractor for FTP configuration."""

    source_config = FTPSourceConfig(
        name="supplier_products_ftp",
        type="ftp",
        host="ftp.example.com",
        username="supplier",
        password_env_var="SUPPLIER_FTP_PASSWORD",
        path=Path("products.csv"),
    )

    extractor = create_factory().create(source_config)

    assert isinstance(extractor, FTPExtractor)
