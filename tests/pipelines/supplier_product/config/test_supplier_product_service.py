from pathlib import Path

import pytest
from src.pipelines.supplier_product.config import (
    SupplierProductConfig,
    SupplierProductService,
)
from src.shared.exceptions import ConfigurationError


def test_service_loads_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / "supplier_product.yaml"

    config_file.write_text(
        """
sources:
    -  name: supplier_products
       type: csv
       path: supplier_products.csv
validation:
    reject_invalid_rows: true
    """,
    )

    service = SupplierProductService(config_path=config_file)
    config = service.get_config()

    assert isinstance(config, SupplierProductConfig)
    assert len(config.sources) == 1
    assert config.sources[0].name == "supplier_products"
    assert config.sources[0].path == Path("supplier_products.csv")
    assert config.validation.reject_invalid_rows is True


def test_service_raises_when_config_file_is_missing(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "supplier_product.yaml"

    service = SupplierProductService(config_path=config_file)

    with pytest.raises(ConfigurationError) as exc:
        service.get_config()

    assert exc.value.error_code == "CONFIG_SUPPLIER_PRODUCT_CONFIG_FILE_NOT_FOUND"


def test_service_rejects_invalid_configuration(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "supplier_product.yaml"
    config_file.write_text(
        """
sources:
    -   name: supplier_products
        type: unsupported
        path: supplier_products.csv
""",
        encoding="utf-8",
    )

    service = SupplierProductService(config_path=config_file)

    with pytest.raises(ConfigurationError) as exc:
        service.get_config()

    assert exc.value.error_code == "CONFIG_SUPPLIER_PRODUCT_CONFIGURATION_INVALID"


def test_service_caches_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / "supplier_product.yaml"
    config_file.write_text(
        """
    sources:
        -   name: supplier_products
            type: csv
            path: supplier_products.csv
    """,
        encoding="utf-8",
    )

    service = SupplierProductService(config_path=config_file)

    first = service.get_config()
    second = service.get_config()

    assert first is second
