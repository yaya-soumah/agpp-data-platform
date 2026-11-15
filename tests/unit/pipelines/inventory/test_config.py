from pathlib import Path

import pytest
from pydantic import ValidationError

from agpp.pipelines.inventory.config import InventoryConfig
from agpp.shared.configuration.service import load_pipeline_config


def _data() -> dict[str, object]:
    return {
        "quality": {
            "max_reject_ratio": 0.05,
            "max_snapshot_age_hours": 26,
            "future_tolerance_minutes": 5,
        },
        "source": {"type": "api", "base_url": "https://stock.example.com", "path": "/v1/stock"},
    }


def _load(project_root: Path, environ: dict[str, str]) -> InventoryConfig:
    return load_pipeline_config(
        project_root / "config", "inventory", InventoryConfig, environ=environ
    )


def test_repository_config_loads_with_defaults(project_root: Path) -> None:
    config = _load(project_root, {})

    assert config.quality.max_snapshot_age_hours == 26
    assert config.source.base_url == "http://localhost:8080"
    assert config.source.path == "/v1/stock"
    assert config.source.token is None
    assert (config.source.timeout_seconds, config.source.page_size) == (10, 500)
    assert config.extraction.max_attempts == 3
    assert config.loading.max_attempts == 3


def test_the_address_and_token_come_from_the_environment(project_root: Path) -> None:
    config = _load(
        project_root,
        {"INVENTORY_API_URL": "https://stock.example.com", "INVENTORY_API_TOKEN": "s3cret"},
    )

    assert config.source.base_url == "https://stock.example.com"
    assert config.source.token is not None
    assert config.source.token.get_secret_value() == "s3cret"
    assert "s3cret" not in repr(config)


def test_retry_settings_have_defaults() -> None:
    config = InventoryConfig.model_validate(_data())

    assert config.extraction.max_attempts == 3
    assert config.loading.initial_delay_seconds == 1.0


@pytest.mark.parametrize(
    "quality",
    [
        {"max_reject_ratio": 1.5},
        {"max_snapshot_age_hours": 0},
        {"future_tolerance_minutes": -1},
    ],
)
def test_invalid_quality_limits_are_rejected(quality: dict[str, object]) -> None:
    data = _data()
    data["quality"] = {**data["quality"], **quality}  # type: ignore[dict-item]

    with pytest.raises(ValidationError):
        InventoryConfig.model_validate(data)


def test_only_api_sources_are_supported() -> None:
    data = _data()
    data["source"] = {"type": "csv", "path": "stock.csv"}

    with pytest.raises(ValidationError, match="source"):
        InventoryConfig.model_validate(data)


def test_unknown_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match="surprise"):
        InventoryConfig.model_validate({**_data(), "surprise": 1})
