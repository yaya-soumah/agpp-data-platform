import asyncio
from pathlib import Path

from src.pipelines.supplier_product import (
    DefaultSupplierProductTransformer,
)
from src.pipelines.supplier_product.config.supplier_product_service import (
    SupplierProductService,
)
from src.pipelines.supplier_product.extractors import SupplierProductExtractorFactory
from src.pipelines.supplier_product.loader import (
    PostgreSQLSupplierProductLoader,
    PostgreSQLSupplierProductWarehouseLoader,
)
from src.pipelines.supplier_product.service import (
    SupplierProductPipelineService,
)
from src.pipelines.supplier_product.validation import (
    DefaultSupplierProductBusinessValidator,
    DefaultSupplierProductDuplicateDetector,
    DefaultSupplierProductSchemaValidator,
)
from src.shared.configuration.environment_resolver import EnvironmentResolver
from src.shared.configuration.runtime import RuntimeEnvironment
from src.shared.configuration.service import ConfigurationService
from src.shared.database.pool import create_postgresql_pool
from src.shared.database.postgresql import PostgreSQLConfigFactory
from src.shared.database.warehouse import PostgreSQLWarehouseSchemaInitializer
from src.shared.logging import configure_logging, get_logger


async def run() -> None:
    """Build the AGPP runtime and execute the supplier-product pipeline."""

    project_root = Path(__file__).resolve().parents[1]
    config_directory = project_root / "config"

    environment_resolver = EnvironmentResolver()
    environment = environment_resolver.resolve()

    configuration = ConfigurationService(
        config_directory=config_directory,
        environment_resolver=environment_resolver,
    ).load(environment)

    app_config = configuration.app

    configure_logging(
        config=configuration.logging,
        environment=environment,
    )

    logger = get_logger("agpp.pipeline.supplier_product")

    runtime_environment = RuntimeEnvironment()

    postgresql_config = PostgreSQLConfigFactory(
        database_config=app_config.database,
        runtime_environment=runtime_environment,
    ).create()

    postgresql_pool = create_postgresql_pool(postgresql_config)

    try:
        postgresql_pool.open()

        warehouse_initializer = PostgreSQLWarehouseSchemaInitializer(
            pool=postgresql_pool,
            warehouse_config=app_config.warehouse,
        )
        warehouse_initializer.initialize()

        supplier_product_service = SupplierProductService(
            config_path=(
                project_root
                / "src"
                / "pipelines"
                / "supplier_product"
                / "config"
                / "supplier_product.yaml"
            ),
        )

        supplier_product_config = supplier_product_service.get_config()

        # Dependencies construction
        extractor_factory = SupplierProductExtractorFactory(
            app_config=app_config,
            runtime_environment=runtime_environment,
            logger=logger,
        )
        schema_validator = DefaultSupplierProductSchemaValidator()
        business_validator = DefaultSupplierProductBusinessValidator()
        duplicate_detector = DefaultSupplierProductDuplicateDetector()
        transformer = DefaultSupplierProductTransformer()
        postgresql_loader = PostgreSQLSupplierProductLoader(
            pool=postgresql_pool, pipeline_config=app_config.pipeline, logger=logger
        )
        warehouse_loader = PostgreSQLSupplierProductWarehouseLoader(
            pool=postgresql_pool,
            pipeline_config=app_config.pipeline,
            warehouse_config=app_config.warehouse,
            logger=logger,
        )

        pipeline = SupplierProductPipelineService(
            extractor_factory=extractor_factory,
            supplier_product_config=supplier_product_config,
            schema_validator=schema_validator,
            business_validator=business_validator,
            duplicate_detector=duplicate_detector,
            transformer=transformer,
            loader=postgresql_loader,
            warehouse_loader=warehouse_loader,
            pipeline_config=app_config.pipeline,
            logger=logger,
        )

        await pipeline.run()

    finally:
        postgresql_pool.close()


def main() -> None:
    """Application entry point."""

    asyncio.run(run())


if __name__ == "__main__":
    main()
