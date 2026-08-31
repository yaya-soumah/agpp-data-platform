from pathlib import Path

import pytest
from pydantic import ValidationError
from src.pipelines.supplier_product.config import (
    CSVSourceConfig,
    SupplierProductConfig,
    SupplierProductSourceType,
    SupplierProductValidationConfig,
)
from src.shared.exceptions import ConfigurationError


@pytest.fixture
def source() -> CSVSourceConfig:
    return CSVSourceConfig(
        name="supplier_products",
        type=SupplierProductSourceType.CSV,
        path=Path("supplier_products.csv"),
    )


def test_valid_source_config(source: CSVSourceConfig) -> None:

    assert source.name == "supplier_products"
    assert source.type == SupplierProductSourceType.CSV
    assert source.path == Path("supplier_products.csv")


def test_source_name_cannot_be_blank() -> None:
    with pytest.raises(ConfigurationError):
        CSVSourceConfig(
            name=" ",
            type=SupplierProductSourceType.CSV,
            path=Path("supplier_product.csv"),
        )


def test_source_type_must_be_supported() -> None:
    with pytest.raises(ValidationError):
        CSVSourceConfig(
            name="supplier_products",
            type="json",
            path=Path("supplier_product.json"),
        )


def test_valid_supplier_product_config() -> None:
    config = SupplierProductConfig(
        sources=[
            CSVSourceConfig(
                name="supplier_master",
                type=SupplierProductSourceType.CSV,
                path=Path("supplier_master.csv"),
            ),
            CSVSourceConfig(
                name="supplier_products",
                type=SupplierProductSourceType.CSV,
                path=Path("supplier_products.csv"),
            ),
        ],
        validation=SupplierProductValidationConfig(
            reject_invalid_rows=True,
        ),
    )

    assert len(config.sources) == 2
    assert config.validation.reject_invalid_rows is True


def test_sources_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        SupplierProductConfig(sources=[])


def test_source_names_must_be_unique(source: CSVSourceConfig) -> None:

    with pytest.raises(ConfigurationError, match="Source names must be unique."):
        SupplierProductConfig(
            sources=[source, source],
        )


def test_validation_config_has_expected_default(source: CSVSourceConfig) -> None:
    config = SupplierProductConfig(
        sources=[
            source,
        ]
    )

    assert config.validation.reject_invalid_rows is True


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SupplierProductConfig(sources=[], unexpected="value")


def test_configuration_is_immutable(source: CSVSourceConfig) -> None:

    config = SupplierProductConfig(
        sources=[
            source,
        ],
    )
    with pytest.raises(ValidationError):
        config.validation = SupplierProductValidationConfig(
            reject_invalid_rows=False,
        )
