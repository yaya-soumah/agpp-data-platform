"""Business models of the Customer Orders pipeline (ADR-0016)."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, Field, field_validator

from agpp.shared.models import AgppModel

CUSTOMER_ID_PATTERN = r"^CUS-\d{5}$"


class OrderStatus(StrEnum):
    """Lifecycle state of an order line."""

    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Customer(AgppModel):
    """A company or person that places orders."""

    customer_id: str = Field(pattern=CUSTOMER_ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(pattern=r"^[A-Z]{2}$")


class OrderLine(AgppModel):
    """One validated row of the order-lines file.

    Values arrive as text; Pydantic converts them. ``customer_id``,
    ``customer_country``, ``product_id`` and ``currency`` are upper-cased,
    ``status`` is lower-cased and timestamps are converted to UTC.
    """

    order_id: str = Field(min_length=1, max_length=30)
    line_number: int = Field(ge=1)
    customer_id: str = Field(pattern=CUSTOMER_ID_PATTERN)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_country: str = Field(pattern=r"^[A-Z]{2}$")
    ordered_at: AwareDatetime
    product_id: str = Field(pattern=r"^SUP-\d{3}:.{1,50}$")
    quantity: int = Field(ge=1, le=10_000)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    status: OrderStatus
    updated_at: AwareDatetime

    @field_validator("customer_id", "customer_country", "product_id", "currency", mode="before")
    @classmethod
    def _uppercase(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("status", mode="before")
    @classmethod
    def _lowercase(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("ordered_at", "updated_at")
    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @property
    def line_amount(self) -> Decimal:
        """Quantity times unit price (no currency conversion, ADR-0016)."""
        return self.quantity * self.unit_price
