"""Business models of the Inventory pipeline (ADR-0018)."""

from datetime import UTC, datetime
from typing import Any

from pydantic import AwareDatetime, Field, field_validator

from agpp.shared.models import AgppModel

LOCATION_CODE_PATTERN = r"^[A-Z]{2}-\d{2}$"


class Location(AgppModel):
    """A place where AGPP holds stock."""

    location_code: str = Field(pattern=LOCATION_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(pattern=r"^[A-Z]{2}$")


class InventoryItem(AgppModel):
    """One validated stock level of a product in a location.

    Values arrive as text; Pydantic converts them. ``location_code``,
    ``location_country`` and ``product_id`` are upper-cased and ``updated_at``
    is converted to UTC.
    """

    location_code: str = Field(pattern=LOCATION_CODE_PATTERN)
    location_name: str = Field(min_length=1, max_length=200)
    location_country: str = Field(pattern=r"^[A-Z]{2}$")
    product_id: str = Field(pattern=r"^SUP-\d{3}:.{1,50}$")
    on_hand: int = Field(ge=0, le=1_000_000)
    reserved: int = Field(ge=0, le=1_000_000)
    reorder_point: int = Field(ge=0, le=1_000_000)
    updated_at: AwareDatetime

    @field_validator("location_code", "location_country", "product_id", mode="before")
    @classmethod
    def _uppercase(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("updated_at")
    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @property
    def available(self) -> int:
        """Stock that can still be promised: on hand minus reserved."""
        return self.on_hand - self.reserved

    @property
    def below_reorder_point(self) -> bool:
        """Whether the available stock has fallen under the reorder point."""
        return self.available < self.reorder_point
