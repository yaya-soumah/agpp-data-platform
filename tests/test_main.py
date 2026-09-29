import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MODULE = "src.main"

PATCHED_NAMES = [
    "EnvironmentResolver",
    "ConfigurationService",
    "RuntimeEnvironment",
    "configure_logging",
    "get_logger",
    "PostgreSQLConfigFactory",
    "create_postgresql_pool",
    "PostgreSQLWarehouseSchemaInitializer",
    "SupplierProductService",
    "SupplierProductExtractorFactory",
    "DefaultSupplierProductSchemaValidator",
    "DefaultSupplierProductBusinessValidator",
    "DefaultSupplierProductDuplicateDetector",
    "DefaultSupplierProductTransformer",
    "PostgreSQLSupplierProductLoader",
    "PostgreSQLSupplierProductWarehouseLoader",
    "SupplierProductPipelineService",
]


@pytest.fixture
def main_module():
    import importlib

    return importlib.import_module(MODULE)


@pytest.fixture
def mocks(main_module):
    """Patch every collaborator used by run() and return them by name."""
    patchers = {name: patch(f"{MODULE}.{name}") for name in PATCHED_NAMES}
    started = {name: p.start() for name, p in patchers.items()}

    # Async pipeline entry point
    started["SupplierProductPipelineService"].return_value.run = AsyncMock()

    # Convenient handles
    started["pool"] = started["create_postgresql_pool"].return_value
    started["pipeline"] = started["SupplierProductPipelineService"].return_value
    started["initializer"] = started[
        "PostgreSQLWarehouseSchemaInitializer"
    ].return_value
    started["configuration"] = started[
        "ConfigurationService"
    ].return_value.load.return_value
    started["environment"] = started[
        "EnvironmentResolver"
    ].return_value.resolve.return_value

    yield started

    for p in patchers.values():
        p.stop()


def _project_root(main_module) -> Path:
    return Path(main_module.__file__).resolve().parents[1]


def test_run_executes_pipeline_and_closes_pool(main_module, mocks):
    asyncio.run(main_module.run())

    mocks["pool"].open.assert_called_once_with()
    mocks["initializer"].initialize.assert_called_once_with()
    mocks["pipeline"].run.assert_awaited_once_with()
    mocks["pool"].close.assert_called_once_with()


def test_run_resolves_environment_and_loads_configuration(main_module, mocks):
    asyncio.run(main_module.run())

    root = _project_root(main_module)
    mocks["ConfigurationService"].assert_called_once_with(
        config_directory=root / "config",
        environment_resolver=mocks["EnvironmentResolver"].return_value,
    )
    mocks["ConfigurationService"].return_value.load.assert_called_once_with(
        mocks["environment"]
    )


def test_run_configures_logging_and_creates_named_logger(main_module, mocks):
    asyncio.run(main_module.run())

    mocks["configure_logging"].assert_called_once_with(
        config=mocks["configuration"].logging,
        environment=mocks["environment"],
    )
    mocks["get_logger"].assert_called_once_with("agpp.pipeline.supplier_product")


def test_run_builds_postgresql_pool_from_config(main_module, mocks):
    asyncio.run(main_module.run())

    app_config = mocks["configuration"].app
    runtime_env = mocks["RuntimeEnvironment"].return_value

    mocks["PostgreSQLConfigFactory"].assert_called_once_with(
        database_config=app_config.database,
        runtime_environment=runtime_env,
    )
    pg_config = mocks["PostgreSQLConfigFactory"].return_value.create.return_value
    mocks["create_postgresql_pool"].assert_called_once_with(pg_config)


def test_run_initializes_warehouse_schema_with_pool_and_config(main_module, mocks):
    asyncio.run(main_module.run())

    mocks["PostgreSQLWarehouseSchemaInitializer"].assert_called_once_with(
        pool=mocks["pool"],
        warehouse_config=mocks["configuration"].app.warehouse,
    )


def test_run_loads_supplier_product_yaml_config(main_module, mocks):
    asyncio.run(main_module.run())

    expected = (
        _project_root(main_module)
        / "src"
        / "pipelines"
        / "supplier_product"
        / "config"
        / "supplier_product.yaml"
    )
    mocks["SupplierProductService"].assert_called_once_with(config_path=expected)
    mocks["SupplierProductService"].return_value.get_config.assert_called_once_with()


def test_run_wires_dependencies_into_pipeline(main_module, mocks):
    asyncio.run(main_module.run())

    app_config = mocks["configuration"].app
    logger = mocks["get_logger"].return_value
    runtime_env = mocks["RuntimeEnvironment"].return_value

    mocks["SupplierProductExtractorFactory"].assert_called_once_with(
        app_config=app_config,
        runtime_environment=runtime_env,
        logger=logger,
    )
    mocks["PostgreSQLSupplierProductLoader"].assert_called_once_with(
        pool=mocks["pool"],
        pipeline_config=app_config.pipeline,
        logger=logger,
    )
    mocks["PostgreSQLSupplierProductWarehouseLoader"].assert_called_once_with(
        pool=mocks["pool"],
        pipeline_config=app_config.pipeline,
        warehouse_config=app_config.warehouse,
        logger=logger,
    )

    mocks["SupplierProductPipelineService"].assert_called_once_with(
        extractor_factory=mocks["SupplierProductExtractorFactory"].return_value,
        supplier_product_config=(
            mocks["SupplierProductService"].return_value.get_config.return_value
        ),
        schema_validator=(mocks["DefaultSupplierProductSchemaValidator"].return_value),
        business_validator=(
            mocks["DefaultSupplierProductBusinessValidator"].return_value
        ),
        duplicate_detector=(
            mocks["DefaultSupplierProductDuplicateDetector"].return_value
        ),
        transformer=mocks["DefaultSupplierProductTransformer"].return_value,
        loader=mocks["PostgreSQLSupplierProductLoader"].return_value,
        warehouse_loader=(
            mocks["PostgreSQLSupplierProductWarehouseLoader"].return_value
        ),
        pipeline_config=app_config.pipeline,
        logger=logger,
    )


def test_pool_is_opened_before_warehouse_init_and_pipeline_run(main_module, mocks):
    order = MagicMock()
    order.attach_mock(mocks["pool"].open, "open")
    order.attach_mock(mocks["initializer"].initialize, "initialize")
    order.attach_mock(mocks["pipeline"].run, "run")
    order.attach_mock(mocks["pool"].close, "close")

    asyncio.run(main_module.run())

    names = [c[0] for c in order.mock_calls]
    assert names == ["open", "initialize", "run", "close"]


def test_pipeline_failure_propagates_and_pool_is_closed(main_module, mocks):
    mocks["pipeline"].run.side_effect = RuntimeError("pipeline boom")

    with pytest.raises(RuntimeError, match="pipeline boom"):
        asyncio.run(main_module.run())

    mocks["pool"].close.assert_called_once_with()


def test_warehouse_init_failure_skips_pipeline_and_closes_pool(main_module, mocks):
    mocks["initializer"].initialize.side_effect = RuntimeError("schema boom")

    with pytest.raises(RuntimeError, match="schema boom"):
        asyncio.run(main_module.run())

    mocks["SupplierProductPipelineService"].assert_not_called()
    mocks["pipeline"].run.assert_not_awaited()
    mocks["pool"].close.assert_called_once_with()


def test_pool_open_failure_still_closes_pool(main_module, mocks):
    mocks["pool"].open.side_effect = ConnectionError("db down")

    with pytest.raises(ConnectionError, match="db down"):
        asyncio.run(main_module.run())

    mocks["initializer"].initialize.assert_not_called()
    mocks["pool"].close.assert_called_once_with()


def test_config_load_failure_never_creates_pool(main_module, mocks):
    mocks["ConfigurationService"].return_value.load.side_effect = ValueError("bad cfg")

    with pytest.raises(ValueError, match="bad cfg"):
        asyncio.run(main_module.run())

    mocks["create_postgresql_pool"].assert_not_called()


def test_main_runs_the_async_entry_point(main_module):
    sentinel = object()

    with (
        patch(
            f"{MODULE}.run", new_callable=MagicMock, return_value=sentinel
        ) as run_mock,
        patch(f"{MODULE}.asyncio.run") as asyncio_run,
    ):
        main_module.main()

    run_mock.assert_called_once_with()
    asyncio_run.assert_called_once_with(sentinel)
