from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call

import polars as pl
import pytest
from src.pipelines.supplier_product.config.models import SupplierProductConfig
from src.pipelines.supplier_product.loader import (
    LoadResult,
    WarehouseLoadResult,
)
from src.pipelines.supplier_product.service import (
    SupplierProductPipelineService,
)
from src.pipelines.supplier_product.validation import ValidationResult
from src.shared.configuration.models import PipelineConfig
from src.shared.exceptions import LoadingError, ValidationError


@pytest.fixture
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        batch_size=1000, retry_attempts=3, max_rejection_ratio=Decimal("0.20")
    )


@pytest.fixture
def extractor_factory() -> MagicMock:
    return MagicMock()


@pytest.fixture
def supplier_product_config() -> MagicMock:
    return MagicMock(spec=SupplierProductConfig)


@pytest.fixture
def schema_validator() -> MagicMock:
    return MagicMock()


@pytest.fixture
def business_validator() -> MagicMock:
    return MagicMock()


@pytest.fixture
def duplicate_detector() -> MagicMock:
    return MagicMock()


@pytest.fixture
def transformer() -> MagicMock:
    return MagicMock()


@pytest.fixture
def loader() -> MagicMock:
    return MagicMock()


@pytest.fixture
def warehouse_loader() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(
    extractor_factory: MagicMock,
    supplier_product_config: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
    pipeline_config: PipelineConfig,
    logger: MagicMock,
) -> SupplierProductPipelineService:
    return SupplierProductPipelineService(
        extractor_factory=extractor_factory,
        supplier_product_config=supplier_product_config,
        schema_validator=schema_validator,
        business_validator=business_validator,
        duplicate_detector=duplicate_detector,
        transformer=transformer,
        loader=loader,
        warehouse_loader=warehouse_loader,
        pipeline_config=pipeline_config,
        logger=logger,
    )


@pytest.mark.asyncio
async def test_extracts_from_all_configured_sources(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
) -> None:
    source_1 = MagicMock()
    source_2 = MagicMock()
    source_3 = MagicMock()

    supplier_product_config.sources = [
        source_1,
        source_2,
        source_3,
    ]

    frame_1 = pl.DataFrame(
        {
            "supplier_product_id": ["P001"],
            "supplier_id": ["S001"],
        }
    )
    frame_2 = pl.DataFrame(
        {
            "supplier_product_id": ["P002"],
            "supplier_id": ["S002"],
        }
    )
    frame_3 = pl.DataFrame(
        {
            "supplier_product_id": ["P003"],
            "supplier_id": ["S003"],
        }
    )

    extractor_1 = MagicMock()
    extractor_1.extract = AsyncMock(return_value=frame_1)

    extractor_2 = MagicMock()
    extractor_2.extract = AsyncMock(return_value=frame_2)

    extractor_3 = MagicMock()
    extractor_3.extract = AsyncMock(return_value=frame_3)

    extractor_factory.create.side_effect = [
        extractor_1,
        extractor_2,
        extractor_3,
    ]

    result = await service._extract()

    expected = pl.concat(
        [frame_1, frame_2, frame_3],
        how="vertical_relaxed",
    )

    assert result.equals(expected)

    assert extractor_factory.create.call_args_list == [
        call(source_1),
        call(source_2),
        call(source_3),
    ]

    extractor_1.extract.assert_awaited_once()
    extractor_2.extract.assert_awaited_once()
    extractor_3.extract.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_passes_validation_results_through_pipeline(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame(
        {
            "supplier_product_id": [
                "P001",
                "P002",
                "P003",
                "P004",
                "P005",
            ]
        }
    )

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    schema_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    business_valid = extracted.head(4)
    business_rejected = extracted.tail(1)

    business_result = ValidationResult(
        valid=business_valid,
        rejected=business_rejected,
    )

    duplicate_valid = extracted.head(4)
    duplicate_rejected = pl.DataFrame({"supplier_product_id": []})

    duplicate_result = ValidationResult(
        valid=duplicate_valid,
        rejected=duplicate_rejected,
    )

    schema_validator.validate.return_value = schema_result
    business_validator.validate.return_value = business_result
    duplicate_detector.detect.return_value = duplicate_result

    transformed = pl.DataFrame(
        {
            "supplier_product_id": [
                "P001",
                "P002",
                "P003",
                "P004",
            ]
        }
    )
    transformer.transform.return_value = transformed

    loader.load.return_value = LoadResult(records_loaded=1)
    warehouse_loader.load.return_value = WarehouseLoadResult(records_loaded=1)

    await service.run()

    schema_validator.validate.assert_called_once_with(extracted)

    business_validator.validate.assert_called_once_with(schema_result)

    duplicate_detector.detect.assert_called_once_with(business_result.valid)

    transformer.transform.assert_called_once_with(duplicate_result.valid)


@pytest.mark.asyncio
async def test_run_returns_aggregated_pipeline_result(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame(
        {
            "supplier_product_id": [
                "P001",
                "P002",
                "P003",
                "P004",
                "P005",
                "P006",
                "P007",
                "P008",
                "P009",
                "P010",
            ],
        }
    )

    schema_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []}, schema={"supplier_product_id": pl.String}
        ),
    )

    business_valid = extracted.head(9)
    business_rejected = extracted.tail(1)

    business_result = ValidationResult(
        valid=business_valid,
        rejected=business_rejected,
    )

    duplicate_valid = business_valid.head(8)
    duplicate_rejected = business_valid.tail(1)

    duplicate_result = ValidationResult(
        valid=duplicate_valid,
        rejected=duplicate_rejected,
    )

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    schema_validator.validate.return_value = schema_result
    business_validator.validate.return_value = business_result
    duplicate_detector.detect.return_value = duplicate_result

    transformed = pl.DataFrame(
        {
            "supplier_product_id": [
                "P001",
                "P002",
                "P003",
                "P004",
                "P005",
                "P006",
                "P007",
                "P008",
            ],
        }
    )
    transformer.transform.return_value = transformed

    operational_result = LoadResult(records_loaded=8)
    warehouse_result = WarehouseLoadResult(records_loaded=8)

    loader.load.return_value = operational_result
    warehouse_loader.load.return_value = warehouse_result

    result = await service.run()

    assert result.records_extracted == 10
    assert result.records_business_rejected == 1
    assert result.records_duplicate_rejected == 1
    assert result.records_valid == 8
    assert result.operational_load == operational_result
    assert result.warehouse_load == warehouse_result


@pytest.mark.asyncio
async def test_run_loads_operational_before_warehouse(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame({"supplier_product_id": ["P001"]})

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    validation_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    schema_validator.validate.return_value = validation_result
    business_validator.validate.return_value = validation_result
    duplicate_detector.detect.return_value = validation_result

    transformed = pl.DataFrame({"supplier_product_id": ["P001"]})
    transformer.transform.return_value = transformed

    events: list[str] = []

    def operational_load(_: pl.DataFrame) -> LoadResult:
        events.append("operational")
        return LoadResult(records_loaded=1)

    def warehouse_load(_: pl.DataFrame) -> WarehouseLoadResult:
        events.append("warehouse")
        return WarehouseLoadResult(records_loaded=1)

    loader.load.side_effect = operational_load
    warehouse_loader.load.side_effect = warehouse_load

    await service.run()

    assert events == ["operational", "warehouse"]


@pytest.mark.asyncio
async def test_run_stops_before_loading_when_quality_threshold_is_exceeded(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame(
        {
            "supplier_product_id": [
                "P001",
                "P002",
                "P003",
                "P004",
                "P005",
            ]
        }
    )

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    schema_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    business_valid = extracted.head(4)
    business_rejected = extracted.tail(1)

    business_result = ValidationResult(
        valid=business_valid,
        rejected=business_rejected,
    )

    duplicate_valid = extracted.head(3)
    duplicate_rejected = extracted.tail(1)

    duplicate_result = ValidationResult(
        valid=duplicate_valid,
        rejected=duplicate_rejected,
    )

    schema_validator.validate.return_value = schema_result
    business_validator.validate.return_value = business_result
    duplicate_detector.detect.return_value = duplicate_result

    with pytest.raises(
        ValidationError,
        match="Validation rejection ratio exceeded the configured pipeline quality threshold.",
    ) as exc_info:
        await service.run()

    assert exc_info.value.error_code == "VALIDATION_REJECTION_THRESHOLD_EXCEEDED"

    transformer.transform.assert_not_called()
    loader.load.assert_not_called()
    warehouse_loader.load.assert_not_called()


@pytest.mark.asyncio
async def test_run_does_not_retry_operational_load(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame({"supplier_product_id": ["P001"]})

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    validation_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    schema_validator.validate.return_value = validation_result
    business_validator.validate.return_value = validation_result
    duplicate_detector.detect.return_value = validation_result

    transformed = pl.DataFrame({"supplier_product_id": ["P001"]})
    transformer.transform.return_value = transformed

    loader.load.side_effect = LoadingError(
        "Temporary database failure.",
        error_code="DATABASE_UNAVAILABLE",
        retryable=True,
    )

    with pytest.raises(LoadingError):
        await service.run()

    loader.load.assert_called_once_with(transformed)


@pytest.mark.asyncio
async def test_run_does_not_load_warehouse_when_operational_load_fails(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame({"supplier_product_id": ["P001"]})

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    validation_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    schema_validator.validate.return_value = validation_result
    business_validator.validate.return_value = validation_result
    duplicate_detector.detect.return_value = validation_result

    transformed = pl.DataFrame({"supplier_product_id": ["P001"]})
    transformer.transform.return_value = transformed

    loader.load.side_effect = LoadingError(
        "Operational database failure.",
        error_code="OPERATIONAL_LOAD_FAILED",
        retryable=False,
    )

    with pytest.raises(LoadingError):
        await service.run()

    warehouse_loader.load.assert_not_called()


@pytest.mark.asyncio
async def test_run_does_not_reload_operational_data_when_warehouse_fails(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame({"supplier_product_id": ["P001"]})

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    validation_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    schema_validator.validate.return_value = validation_result
    business_validator.validate.return_value = validation_result
    duplicate_detector.detect.return_value = validation_result

    transformed = pl.DataFrame({"supplier_product_id": ["P001"]})
    transformer.transform.return_value = transformed

    loader.load.return_value = LoadResult(records_loaded=1)

    warehouse_loader.load.side_effect = LoadingError(
        "Warehouse load failed.",
        error_code="WAREHOUSE_LOAD_FAILED",
        retryable=False,
    )

    with pytest.raises(LoadingError):
        await service.run()

    loader.load.assert_called_once_with(transformed)
    warehouse_loader.load.assert_called_once_with(transformed)


@pytest.mark.asyncio
async def test_run_logs_pipeline_lifecycle(
    service: SupplierProductPipelineService,
    supplier_product_config: MagicMock,
    extractor_factory: MagicMock,
    schema_validator: MagicMock,
    business_validator: MagicMock,
    duplicate_detector: MagicMock,
    transformer: MagicMock,
    loader: MagicMock,
    warehouse_loader: MagicMock,
    logger: MagicMock,
) -> None:
    source = MagicMock()
    supplier_product_config.sources = [source]

    extracted = pl.DataFrame({"supplier_product_id": ["P001"]})

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=extracted)
    extractor_factory.create.return_value = extractor

    validation_result = ValidationResult(
        valid=extracted,
        rejected=pl.DataFrame(
            {"supplier_product_id": []},
            schema={"supplier_product_id": pl.String},
        ),
    )

    schema_validator.validate.return_value = validation_result
    business_validator.validate.return_value = validation_result
    duplicate_detector.detect.return_value = validation_result

    transformer.transform.return_value = extracted
    loader.load.return_value = LoadResult(records_loaded=1)
    warehouse_loader.load.return_value = WarehouseLoadResult(records_loaded=1)

    await service.run()

    info_messages = [call.args[0] for call in logger.info.call_args_list]

    assert "Supplier product pipeline started." in info_messages
    assert "Supplier product pipeline completed." in info_messages
