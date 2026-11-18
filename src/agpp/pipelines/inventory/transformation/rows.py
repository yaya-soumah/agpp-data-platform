"""Warehouse-shaped rows produced by the transformation (ADR-0018)."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import AwareDatetime

from agpp.shared.models import AgppModel


class LocationRow(AgppModel):
    """A row for ``warehouse.dim_location`` (business key: ``location_code``)."""

    location_code: str
    location_name: str
    country: str
    source_updated_at: AwareDatetime


class SnapshotRow(AgppModel):
    """A row for ``warehouse.fact_inventory_snapshot``.

    The surrogate keys of the location and the product are resolved by the loader.
    """

    location_code: str
    product_id: str
    on_hand: int
    reserved: int
    available: int
    reorder_point: int
    below_reorder_point: bool
    source_updated_at: AwareDatetime


@dataclass(frozen=True)
class TransformedInventory:
    """Everything to load for one run: the snapshot time, its date key and the rows."""

    snapshot_at: datetime
    date_key: int
    locations: tuple[LocationRow, ...]
    rows: tuple[SnapshotRow, ...]
