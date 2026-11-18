"""Pure transformation of validated stock items into warehouse rows (ADR-0013, ADR-0018)."""

from collections.abc import Sequence
from datetime import datetime

from agpp.pipelines.inventory.models import InventoryItem
from agpp.pipelines.inventory.transformation.rows import (
    LocationRow,
    SnapshotRow,
    TransformedInventory,
)
from agpp.shared.dates.datetime_utils import date_key
from agpp.shared.exceptions import TransformationError
from agpp.shared.text import collapse_whitespace

__all__ = ["collapse_whitespace", "to_rows"]


def to_rows(snapshot_at: datetime, items: Sequence[InventoryItem]) -> TransformedInventory:
    """Map validated items to snapshot rows and their distinct locations.

    The date key is the UTC date of the snapshot. A location takes its name and
    country from its most recently updated item (the later item on a tie). Raises
    ``TransformationError`` if the same location and product appear twice, which
    would mean a bug upstream.
    """
    seen: set[tuple[str, str]] = set()
    newest: dict[str, InventoryItem] = {}
    rows: list[SnapshotRow] = []
    for item in items:
        key = (item.location_code, item.product_id)
        if key in seen:
            raise TransformationError(
                "Duplicate stock item after validation",
                context={"location_code": item.location_code, "product_id": item.product_id},
            )
        seen.add(key)

        current = newest.get(item.location_code)
        if current is None or item.updated_at >= current.updated_at:
            newest[item.location_code] = item

        rows.append(
            SnapshotRow(
                location_code=item.location_code,
                product_id=item.product_id,
                on_hand=item.on_hand,
                reserved=item.reserved,
                available=item.available,
                reorder_point=item.reorder_point,
                below_reorder_point=item.below_reorder_point,
                source_updated_at=item.updated_at,
            )
        )

    locations = tuple(
        LocationRow(
            location_code=code,
            location_name=collapse_whitespace(item.location_name),
            country=item.location_country,
            source_updated_at=item.updated_at,
        )
        for code, item in sorted(newest.items())
    )
    return TransformedInventory(
        snapshot_at=snapshot_at,
        date_key=date_key(snapshot_at.date()),
        locations=locations,
        rows=tuple(rows),
    )
