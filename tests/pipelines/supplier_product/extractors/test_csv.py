from pathlib import Path
from unittest.mock import Mock

import polars as pl
import pytest
from src.pipelines.supplier_product import CSVExtractor
from src.pipelines.supplier_product.config import (
    SupplierProductSourceConfig,
    SupplierProductSourceType,
)
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
def source_config() -> SupplierProductSourceConfig:
    return SupplierProductSourceConfig(
        name="supplier_products",
        type=SupplierProductSourceType.CSV,
        path=Path("supplier_products.csv"),
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


def _with_raw_data(app_config: AppConfig, raw_data_path: Path) -> AppConfig:
    """Returns a copy of app_config pointing raw_data at the given path."""
    return app_config.model_copy(
        update={
            "paths": app_config.paths.model_copy(
                update={"raw_data": str(raw_data_path)}
            )
        }
    )


def test_extract_returns_dataframe(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:

    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    source_path = raw_data_path / source_config.path
    source_path.write_text(
        "supplier_id,product_id,price\nS001,P001,10.50\nS002,P002,20.75\n",
        encoding="utf-8",
    )

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    result = extractor.extract()

    assert isinstance(result, pl.DataFrame)
    assert result.height == 2
    assert result.width == 3
    assert result.columns == ["supplier_id", "product_id", "price"]


def test_reads_file_relative_to_raw_data_directory(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:
    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    source_path = raw_data_path / "supplier_products.csv"
    source_path.write_text(
        "supplier_id,product_id\nS001,P001\n",
        encoding="utf-8",
    )

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    result = extractor.extract()

    assert result.to_dicts() == [
        {"supplier_id": "S001", "product_id": "P001"},
    ]


def test_extract_returns_empty_dataframe_for_header_only_csv(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:
    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    source_path = raw_data_path / source_config.path
    source_path.write_text("supplier_id,product_id,price\n", encoding="utf-8")

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    result = extractor.extract()

    assert isinstance(result, pl.DataFrame)
    assert result.height == 0
    assert result.width == 3


def test_extract_raises_data_extraction_error_on_malformed_csv(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:

    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    source_path = raw_data_path / source_config.path
    source_path.write_text(
        "supplier_id,product_id,price\n"
        "S001,P001,10.50\n"
        "S002,P002,20.75,UNEXPECTED_EXTRA_FIELD\n",  # extra field -> ragged line
        encoding="utf-8",
    )

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    with pytest.raises(DataExtractionError) as exc_info:
        extractor.extract()

    assert exc_info.value.error_code == "EXTRACT_CSV_FAILED"
    logger.error.assert_called_once()


def test_extract_missing_file_raises_file_not_found_error(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:

    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    with pytest.raises(DataExtractionError) as exc_info:
        extractor.extract()

    assert exc_info.value.error_code == "EXTRACT_CSV_FAILED"
    logger.error.assert_called_once()


def test_extract_logs_success(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:
    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    source_path = raw_data_path / source_config.path
    source_path.write_text(
        "supplier_id,product_id,price\nS001,P001,10.50\nS002,P002,20.75\n",
        encoding="utf-8",
    )

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    extractor.extract()

    assert logger.info.call_count == 2
    logger.error.assert_not_called()


def test_extract_logs_error_on_failure(
    tmp_path: Path,
    app_config: AppConfig,
    source_config: SupplierProductSourceConfig,
    logger: Mock,
) -> None:
    raw_data_path = tmp_path / "raw"
    raw_data_path.mkdir()

    app_config = _with_raw_data(app_config, raw_data_path)

    extractor = CSVExtractor(
        app_config=app_config,
        source_config=source_config,
        logger=logger,
    )

    with pytest.raises(DataExtractionError):
        extractor.extract()

    logger.error.assert_called_once()
