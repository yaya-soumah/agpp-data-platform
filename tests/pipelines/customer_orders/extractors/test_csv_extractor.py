import polars as pl
import pytest


from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from src.pipelines.customer_orders.extractors import CustomerOrderCSVExtractor
from src.pipelines.customer_orders.models import (
    CUSTOMER_SCHEMA,
    ORDER_LINE_SCHEMA,
    ORDER_SCHEMA,
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
def app_config() -> AppConfig:
    return AppConfig(
        application=ApplicationConfig(
            name="AGPP Data Platform",
            version="0.1.0",
        ),
        environment_name=Environment.DEVELOPMENT,
        environment=EnvironmentConfig(timezone="UTC"),
        pipeline=PipelineConfig(
            batch_size=1000, retry_attempts=3, max_rejection_ratio=Decimal("0.20")
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

def write_batch(directory: Path) -> Path:
    
    raw_data_path = directory / "raw"
    raw_data_path.mkdir(parents=True, exist_ok=True)

    customer_path = raw_data_path / "customers.csv"
    customer_path.write_text(
        "customer_id,name\nC001,Acme Ltd\n",
        encoding="utf-8",
    )

    order_path = raw_data_path / "orders.csv"
    order_path.write_text(
        "order_id,customer_id,ordered_at,status,cancelled_at\n"
        "o001,C001,2025-10-01T10:00:00Z,PLACED,\n",
        encoding="utf-8",
    )

    order_lines_path = raw_data_path / "order_lines.csv"
    order_lines_path.write_text(
        "order_line_id,order_id,product_id,quantity,"
        "unit_price_amount,unit_price_currency\n"
        "L001,o001,P001,2,19.95,USD\n",
        encoding="utf-8",
    )
    return raw_data_path

def update_app_config(app_config: AppConfig, directory: Path)-> AppConfig:
    return app_config.model_copy(
        update={
            "paths": app_config.paths.model_copy(
                update={
                    "raw_data": str(directory)
                }
            )
        }
    )

def test_extract_returns_all_three_datasets(
        tmp_path,
        app_config,
        logger
    )->None:
            
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config,raw_data_path)

    batch = CustomerOrderCSVExtractor(
        app_config=app_config,
        logger=logger
    ).extract()

    assert batch.customers.shape == (1,2)
    assert batch.orders.shape == (1,5)
    assert batch.order_lines.shape == (1,6)

    assert batch.customers["customer_id"].to_list() == ["C001"]
    assert batch.orders["order_id"].to_list() == ["o001"]
    assert batch.order_lines["order_line_id"].to_list() == ["L001"]

def test_extract_preserves_source_values_as_strings(
        tmp_path,
        app_config,
        logger
    )->None:
            
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config,raw_data_path)

    batch = CustomerOrderCSVExtractor(
        app_config=app_config,
        logger=logger
    ).extract()

    assert batch.orders["ordered_at"].dtype == pl.String
    assert batch.order_lines["quantity"].dtype == pl.String
    assert batch.order_lines["unit_price_amount"].dtype == pl.String

def test_extract_fails_if_a_file_is_missing(tmp_path, app_config, logger) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config,raw_data_path)
    
    (raw_data_path / "orders.csv").unlink()

    with pytest.raises(DataExtractionError):
        CustomerOrderCSVExtractor(
        app_config=app_config,
        logger=logger
    ).extract()

def test_extract_fails_when_a_column_is_missing(tmp_path, app_config, logger) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    # Drop the "status" column from orders.csv
    (raw_data_path / "orders.csv").write_text(
        "order_id,customer_id,ordered_at,cancelled_at\n"
        "o001,C001,2025-10-01T10:00:00Z,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataExtractionError) as exc_info:
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert exc_info.value.error_code == "EXTRACT_CUSTOMER_ORDERS_SCHEMA_INVALID"
    assert "orders.csv" in str(exc_info.value)

def test_extract_fails_when_an_extra_column_is_present(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    (raw_data_path / "customers.csv").write_text(
        "customer_id,name,extra\nC001,Acme Ltd,x\n", encoding="utf-8"
    )

    with pytest.raises(DataExtractionError) as exc_info:
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert exc_info.value.error_code == "EXTRACT_CUSTOMER_ORDERS_SCHEMA_INVALID"

def test_extract_fails_when_column_is_renamed(tmp_path, app_config, logger) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    (raw_data_path / "customers.csv").write_text(
        "customer_id,full_name\nC001,Acme Ltd\n", encoding="utf-8"
    )

    with pytest.raises(DataExtractionError) as exc_info:
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert exc_info.value.error_code == "EXTRACT_CUSTOMER_ORDERS_SCHEMA_INVALID"

def test_extract_normalizes_column_order_for_orders(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    (raw_data_path / "orders.csv").write_text(
        "status,order_id,cancelled_at,customer_id,ordered_at\n"
        "PLACED,o001,,C001,2025-10-01T10:00:00Z\n",
        encoding="utf-8",
    )

    batch = CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert batch.orders.columns == list(ORDER_SCHEMA)
    assert batch.orders.row(0) == (
        "o001",
        "C001",
        "2025-10-01T10:00:00Z",
        "PLACED",
        None,
    )

def test_extract_normalizes_column_order_for_order_lines(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    (raw_data_path / "order_lines.csv").write_text(
        "unit_price_currency,order_line_id,quantity,order_id,"
        "unit_price_amount,product_id\n"
        "USD,L001,2,o001,19.95,P001\n",
        encoding="utf-8",
    )

    batch = CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert batch.order_lines.columns == list(ORDER_LINE_SCHEMA)
    assert batch.order_lines.row(0) == (
        "L001",
        "o001",
        "P001",
        "2",
        "19.95",
        "USD",
    )

def test_extract_chains_underlying_exception_on_missing_file(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)
    (raw_data_path / "customers.csv").unlink()

    with pytest.raises(DataExtractionError) as exc_info:
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert exc_info.value.error_code == "EXTRACT_CUSTOMER_ORDERS_CSV_FAILED"
    # Polars surfaces missing files as an OSError; the cause must be preserved.
    assert isinstance(exc_info.value.__cause__, (OSError, pl.exceptions.PolarsError))


def test_extract_chains_underlying_exception_on_malformed_csv(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    # Ragged CSV: row has more fields than the header.
    (raw_data_path / "customers.csv").write_text(
        "customer_id,name\nC001,Acme Ltd,EXTRA\n", encoding="utf-8"
    )

    with pytest.raises(DataExtractionError) as exc_info:
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert exc_info.value.error_code == "EXTRACT_CUSTOMER_ORDERS_CSV_FAILED"
    assert exc_info.value.__cause__ is not None


def test_extract_does_not_leak_partial_batch_on_failure(
    tmp_path, app_config, logger
) -> None:
    """If a later file fails, no batch is returned (no silent partial success)."""
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)
    (raw_data_path / "order_lines.csv").unlink()

    with pytest.raises(DataExtractionError):
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

def test_extract_logs_start_and_success(tmp_path, app_config, logger) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    info_messages = [call.args[0] for call in logger.info.call_args_list]
    assert any("Starting customer-orders CSV extraction" in m for m in info_messages)
    assert any(
        "Customer-orders CSV extraction completed successfully" in m
        for m in info_messages
    )
    assert logger.error.call_count == 0


def test_extract_logs_error_on_failure(tmp_path, app_config, logger) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)
    (raw_data_path / "orders.csv").unlink()

    with pytest.raises(DataExtractionError):
        CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert logger.error.call_count == 1
    fmt, path_arg, _exc = logger.error.call_args.args
    assert fmt == "Customer-orders CSV extractor failed for '%s': %s"
    assert path_arg.name == "orders.csv"

def test_extract_succeeds_with_header_only_csv(tmp_path, app_config, logger) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    (raw_data_path / "customers.csv").write_text(
        "customer_id,name\n", encoding="utf-8"
    )

    batch = CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert batch.customers.shape == (0, 2)
    assert batch.customers.columns == list(CUSTOMER_SCHEMA)
    assert batch.orders.shape == (1, 5)  # other files untouched


def test_extract_keeps_numeric_looking_strings_as_strings(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    # A value that *would* be inferred as an integer without infer_schema_length=0.
    (raw_data_path / "order_lines.csv").write_text(
        "order_line_id,order_id,product_id,quantity,"
        "unit_price_amount,unit_price_currency\n"
        "123,o001,P001,2,19.95,USD\n",
        encoding="utf-8",
    )

    batch = CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    assert batch.order_lines["order_line_id"].dtype == pl.String
    assert batch.order_lines["order_line_id"].to_list() == ["123"]

def test_extract_wires_frames_to_correct_batch_attributes(
    tmp_path, app_config, logger
) -> None:
    raw_data_path = write_batch(tmp_path)
    app_config = update_app_config(app_config, raw_data_path)

    batch = CustomerOrderCSVExtractor(app_config=app_config, logger=logger).extract()

    # Each frame must be the one read from its matching filename.
    assert batch.customers.columns == list(CUSTOMER_SCHEMA)
    assert batch.orders.columns == list(ORDER_SCHEMA)
    assert batch.order_lines.columns == list(ORDER_LINE_SCHEMA)
    assert batch.customers["customer_id"].to_list() == ["C001"]
    assert batch.orders["order_id"].to_list() == ["o001"]
    assert batch.order_lines["order_line_id"].to_list() == ["L001"]