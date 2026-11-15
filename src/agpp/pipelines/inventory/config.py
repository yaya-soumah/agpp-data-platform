"""Configuration model of the Inventory pipeline (ADR-0018)."""

from pydantic import Field

from agpp.shared.extraction import ApiSource
from agpp.shared.models import AgppModel
from agpp.shared.resilience.config import RetryConfig


class QualityConfig(AgppModel):
    """Limits used by business validation and the quality gate."""

    max_reject_ratio: float = Field(ge=0, le=1)
    max_snapshot_age_hours: int = Field(ge=1)
    future_tolerance_minutes: int = Field(ge=0)


class InventoryConfig(AgppModel):
    """Everything the pipeline reads from ``config/pipelines/inventory.yaml``."""

    quality: QualityConfig
    source: ApiSource
    extraction: RetryConfig = Field(default_factory=RetryConfig)
    loading: RetryConfig = Field(default_factory=RetryConfig)
