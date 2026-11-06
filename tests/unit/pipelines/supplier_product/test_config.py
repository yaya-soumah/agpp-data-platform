from pathlib import Path

import pytest
from pydantic import ValidationError

from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.shared.configuration.service import load_pipeline_config


def _data() -> dict[str, object]:
    def supplier(number: str) -> dict[str, object]:
        return {
            "supplier_id": f"SUP-{number}",
            "name": f"Supplier {number}",
            "country": "LU",
            "source": {"type": "csv", "path": f"{number}.csv"},
        }

    return {
        "quality": {
            "max_reject_ratio": 0.1,
            "allowed_currencies": ["EUR"],
            "max_unit_price": 1000,
            "future_tolerance_minutes": 5,
        },
        "suppliers": [supplier("001"), supplier("002")],
    }


def test_repository_config_loads(project_root: Path) -> None:
    config = load_pipeline_config(
        project_root / "config", "supplier_product", SupplierProductConfig, environ={}
    )

    assert [s.supplier_id for s in config.suppliers] == ["SUP-001", "SUP-002", "SUP-003"]
    assert config.quality.max_reject_ratio == 0.10
    assert config.quality.allowed_currencies == ("EUR", "USD", "GBP", "CHF")
    assert config.suppliers[1].source.delimiter == ";"
    assert config.suppliers[0].source.path == "data/incoming/supplier_product/sup-001.csv"


def test_data_directory_can_be_relocated_with_a_variable(project_root: Path) -> None:
    config = load_pipeline_config(
        project_root / "config",
        "supplier_product",
        SupplierProductConfig,
        environ={"AGPP_DATA_DIR": "/srv/agpp"},
    )

    assert config.suppliers[0].source.path == "/srv/agpp/incoming/supplier_product/sup-001.csv"


def test_valid_data_is_accepted() -> None:
    config = SupplierProductConfig.model_validate(_data())

    assert len(config.suppliers) == 2


def test_duplicate_supplier_ids_are_rejected() -> None:
    data = _data()
    data["suppliers"] = [data["suppliers"][0], data["suppliers"][0]]  # type: ignore[index]

    with pytest.raises(ValidationError, match="duplicate supplier ids"):
        SupplierProductConfig.model_validate(data)


def test_unsupported_source_types_are_rejected() -> None:
    data = _data()
    data["suppliers"][0]["source"] = {"type": "ftp", "path": "x"}  # type: ignore[index]

    with pytest.raises(ValidationError, match="source"):
        SupplierProductConfig.model_validate(data)


def test_reject_ratio_must_be_between_zero_and_one() -> None:
    data = _data()
    data["quality"]["max_reject_ratio"] = 1.5  # type: ignore[index]

    with pytest.raises(ValidationError, match="max_reject_ratio"):
        SupplierProductConfig.model_validate(data)


def test_extraction_settings_come_from_the_yaml(project_root: Path) -> None:
    config = load_pipeline_config(
        project_root / "config", "supplier_product", SupplierProductConfig, environ={}
    )

    assert config.extraction.max_attempts == 3
    assert config.extraction.initial_delay_seconds == 1.0


def test_extraction_settings_have_defaults() -> None:
    config = SupplierProductConfig.model_validate(_data())

    assert config.extraction.max_attempts == 3


def test_extraction_attempts_must_be_at_least_one() -> None:
    data = _data()
    data["extraction"] = {"max_attempts": 0}

    with pytest.raises(ValidationError, match="max_attempts"):
        SupplierProductConfig.model_validate(data)


def test_loading_settings_come_from_the_yaml(project_root: Path) -> None:
    config = load_pipeline_config(
        project_root / "config", "supplier_product", SupplierProductConfig, environ={}
    )

    assert config.loading.max_attempts == 3
    assert config.loading.initial_delay_seconds == 1.0


def test_loading_attempts_must_be_at_least_one() -> None:
    data = _data()
    data["loading"] = {"max_attempts": 0}

    with pytest.raises(ValidationError, match="max_attempts"):
        SupplierProductConfig.model_validate(data)
