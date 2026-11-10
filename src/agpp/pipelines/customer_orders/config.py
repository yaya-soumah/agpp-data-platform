"""Configuration model of the Customer Orders pipeline (ADR-0016)."""

from decimal import Decimal

from pydantic import Field

from agpp.shared.extraction import CsvSource
from agpp.shared.models import AgppModel
from agpp.shared.models.types import CurrencyCode
from agpp.shared.resilience.config import RetryConfig


class QualityConfig(AgppModel):
    """Limits used by business validation and the quality gate."""

    max_reject_ratio: float = Field(ge=0, le=1)
    allowed_currencies: tuple[CurrencyCode, ...] = Field(min_length=1)
    max_line_amount: Decimal = Field(gt=0)
    future_tolerance_minutes: int = Field(ge=0)


class CustomerOrdersConfig(AgppModel):
    """Everything the pipeline reads from ``config/pipelines/customer_orders.yaml``."""

    quality: QualityConfig
    source: CsvSource
    extraction: RetryConfig = Field(default_factory=RetryConfig)
    loading: RetryConfig = Field(default_factory=RetryConfig)
