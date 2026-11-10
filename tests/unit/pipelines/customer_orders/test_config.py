from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.shared.configuration.service import load_pipeline_config


def _data() -> dict[str, object]:
    return {
        "quality": {
            "max_reject_ratio": 0.05,
            "allowed_currencies": ["EUR"],
            "max_line_amount": 1000,
            "future_tolerance_minutes": 5,
        },
        "source": {"type": "csv", "path": "orders.csv"},
    }


def test_repository_config_loads(project_root: Path) -> None:
    config = load_pipeline_config(
        project_root / "config", "customer_orders", CustomerOrdersConfig, environ={}
    )

    assert config.quality.max_reject_ratio == 0.05
    assert config.quality.allowed_currencies == ("EUR", "USD", "GBP", "CHF")
    assert config.quality.max_line_amount == Decimal("1000000")
    assert config.source.path == "data/incoming/customer_orders/orders.csv"
    assert config.extraction.max_attempts == 3
    assert config.loading.max_attempts == 3


def test_the_data_directory_can_be_relocated_with_a_variable(project_root: Path) -> None:
    config = load_pipeline_config(
        project_root / "config",
        "customer_orders",
        CustomerOrdersConfig,
        environ={"AGPP_DATA_DIR": "/srv/agpp"},
    )

    assert config.source.path == "/srv/agpp/incoming/customer_orders/orders.csv"


def test_retry_settings_have_defaults() -> None:
    config = CustomerOrdersConfig.model_validate(_data())

    assert config.extraction.max_attempts == 3
    assert config.loading.initial_delay_seconds == 1.0


def test_the_reject_ratio_must_be_between_zero_and_one() -> None:
    data = _data()
    data["quality"] = {**data["quality"], "max_reject_ratio": 1.5}  # type: ignore[dict-item]

    with pytest.raises(ValidationError, match="max_reject_ratio"):
        CustomerOrdersConfig.model_validate(data)


def test_only_csv_sources_are_supported() -> None:
    data = _data()
    data["source"] = {"type": "ftp", "path": "x"}

    with pytest.raises(ValidationError, match="source"):
        CustomerOrdersConfig.model_validate(data)


def test_unknown_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match="surprise"):
        CustomerOrdersConfig.model_validate({**_data(), "surprise": 1})
