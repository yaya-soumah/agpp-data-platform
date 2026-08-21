from pydantic import BaseModel,Field, ConfigDict
from decimal import Decimal
from src.shared.currency import Money

class SupplierProduct(BaseModel):

    """Business entity representing a product offered by a supplier."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    supplier_product_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    supplier_sku: str | None = None
    name: str = Field(min_length=1)
    description: setattr | None = None
    price: Money | None = None
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, gt=0)
