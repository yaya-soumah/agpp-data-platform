from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

class SupplierProductRecord(BaseModel):
    """Source-level supplier product record."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    supplier_product_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    supplier_sku: str | None = None
    name:str = Field(min_length=1)
    description: str | None = None
    price: str | None = None
    currency: str |None = None
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0)


class ValidateSupplierProductRecord(SupplierProductRecord):
    """Supplier product record that passed pipeline validation."""

    pass