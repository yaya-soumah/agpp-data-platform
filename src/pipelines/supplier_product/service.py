from dataclasses import dataclass
from logging import Logger

import polars as pl
from src.pipelines.supplier_product.config.models import SupplierProductConfig
from src.pipelines.supplier_product.extractors import SupplierProductExtractorFactory
from src.pipelines.supplier_product.loader import (
    LoadResult,
    SupplierProductLoader,
    SupplierProductWarehouseLoader,
    WarehouseLoadResult,
)
from src.pipelines.supplier_product.transformer import DefaultSupplierProductTransformer
from src.pipelines.supplier_product.validation import (
    DefaultSupplierProductBusinessValidator,
    DefaultSupplierProductDuplicateDetector,
    DefaultSupplierProductSchemaValidator,
)
from src.shared.configuration.models import PipelineConfig
from src.shared.orchestration.validation_quality import ValidationQualityPolicy


@dataclass(frozen=True)
class SupplierProductPipelineResult:
    """Result of a supplier product pipeline execution."""

    records_extracted: int
    records_business_rejected: int
    records_duplicate_rejected: int
    records_valid: int
    operational_load: LoadResult
    warehouse_load: WarehouseLoadResult


class SupplierProductPipelineService:
    """Orchestrates the supplier product pipeline lifecycle."""

    def __init__(
        self,
        extractor_factory: SupplierProductExtractorFactory,
        supplier_product_config: SupplierProductConfig,
        schema_validator: DefaultSupplierProductSchemaValidator,
        business_validator: DefaultSupplierProductBusinessValidator,
        duplicate_detector: DefaultSupplierProductDuplicateDetector,
        transformer: DefaultSupplierProductTransformer,
        loader: SupplierProductLoader,
        warehouse_loader: SupplierProductWarehouseLoader,
        pipeline_config: PipelineConfig,
        logger: Logger,
    ) -> None:
        self._extractor_factory = extractor_factory
        self._supplier_product_config = supplier_product_config
        self._schema_validator = schema_validator
        self._business_validator = business_validator
        self._duplicate_detector = duplicate_detector
        self._transformer = transformer
        self._loader = loader
        self._warehouse_loader = warehouse_loader
        self._logger = logger
        self._validation_quality_policy = ValidationQualityPolicy(
            max_rejection_ratio=pipeline_config.max_rejection_ratio,
        )

    async def run(self) -> SupplierProductPipelineResult:
        """Execute the Supplier Product pipeline."""

        self._logger.info("Supplier product pipeline started.")

        extracted_records = await self._extract()
        records_extracted = extracted_records.height

        schema_result = self._schema_validator.validate(extracted_records)
        business_result = self._business_validator.validate(schema_result)

        duplicate_result = self._duplicate_detector.detect(business_result.valid)

        records_business_rejected = business_result.rejected.height
        records_duplicate_rejected = duplicate_result.rejected.height

        records_valid = duplicate_result.valid.height
        records_rejected = records_business_rejected + records_duplicate_rejected

        self._logger.info(
            "Supplier product validation completed: "
            "%d extracted, "
            "%d business rejected, % duplicate rejected, "
            "%d valid.",
            records_extracted,
            records_business_rejected,
            records_duplicate_rejected,
            records_valid,
        )

        quality_result = self._validation_quality_policy.evaluate(
            records_extracted=records_extracted,
            records_valid=records_valid,
            records_rejected=records_rejected,
        )

        self._logger.info(
            "Supplier product validation quality accepted: rejection ratio %.4f",
            quality_result.rejection_ratio,
        )

        transformed_records = self._transformer.transform(duplicate_result.valid)

        self._logger.info(
            "Supplier product transformation completed: %d records.",
            transformed_records.height,
        )

        operational_result = self._loader.load(transformed_records)

        self._logger.info(
            "Operational supplier product load completed: %d records.",
            operational_result.records_loaded,
        )
        warehouse_result = self._warehouse_loader.load(transformed_records)
        self._logger.info(
            "Supplier product warehouse load completed: %d records.",
            warehouse_result.records_loaded,
        )

        self._logger.info("Supplier product pipeline completed.")

        return SupplierProductPipelineResult(
            records_extracted=records_extracted,
            records_business_rejected=records_business_rejected,
            records_duplicate_rejected=records_duplicate_rejected,
            records_valid=records_valid,
            operational_load=operational_result,
            warehouse_load=warehouse_result,
        )

    async def _extract(self) -> pl.DataFrame:
        """Extract and combine data from all configured sources."""

        frames: list[pl.DataFrame] = []

        for source_config in self._supplier_product_config.sources:
            extractor = self._extractor_factory.create(source_config)

            frames.append(await extractor.extract())

        return pl.concat(frames, how="vertical_relaxed")
