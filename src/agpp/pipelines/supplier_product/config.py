"""Configuration model of the Supplier Product pipeline (ADR-0010)."""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from agpp.pipelines.supplier_product.models import Supplier
from agpp.shared.models import AgppModel
from agpp.shared.resilience.config import RetryConfig

CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class CsvSource(AgppModel):
    """A supplier file in CSV format."""

    type: Literal["csv"]
    path: str = Field(min_length=1)
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: str = "utf-8"


class SupplierConfig(Supplier):
    """A supplier together with where its catalog comes from."""

    source: CsvSource


class QualityConfig(AgppModel):
    """Limits used by business validation and the quality gate."""

    max_reject_ratio: float = Field(ge=0, le=1)
    allowed_currencies: tuple[CurrencyCode, ...] = Field(min_length=1)
    max_unit_price: Decimal = Field(gt=0)
    future_tolerance_minutes: int = Field(ge=0)


class SupplierProductConfig(AgppModel):
    """Everything the pipeline reads from ``config/pipelines/supplier_product.yaml``."""

    quality: QualityConfig
    suppliers: tuple[SupplierConfig, ...] = Field(min_length=1)
    extraction: RetryConfig = Field(default_factory=RetryConfig)
    loading: RetryConfig = Field(default_factory=RetryConfig)

    @model_validator(mode="after")
    def _unique_supplier_ids(self) -> Self:
        ids = [supplier.supplier_id for supplier in self.suppliers]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ValueError(f"duplicate supplier ids: {duplicates}")
        return self
