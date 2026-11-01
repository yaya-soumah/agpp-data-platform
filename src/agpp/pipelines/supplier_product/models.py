"""Business models of the Supplier Product pipeline (ADR-0010)."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AwareDatetime, Field, field_validator

from agpp.shared.models import AgppModel

SUPPLIER_ID_PATTERN = r"^SUP-\d{3}$"


class Supplier(AgppModel):
    """A company AGPP buys products from."""

    supplier_id: str = Field(pattern=SUPPLIER_ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(pattern=r"^[A-Z]{2}$")


class SupplierProduct(AgppModel):
    """One validated row of a supplier catalog.

    Values arrive as text from files; Pydantic converts them. ``supplier_sku``
    and ``currency`` are upper-cased and ``updated_at`` is converted to UTC.
    """

    supplier_id: str = Field(pattern=SUPPLIER_ID_PATTERN)
    supplier_sku: str = Field(min_length=1, max_length=50)
    product_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    min_order_quantity: int = Field(default=1, ge=1)
    lead_time_days: int = Field(ge=0, le=365)
    is_active: bool = True
    updated_at: AwareDatetime

    @field_validator("supplier_sku", "currency")
    @classmethod
    def _uppercase(cls, value: str) -> str:
        return value.upper()

    @field_validator("updated_at")
    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
