"""Synthetic stock feed for development and demos (ADR-0018).

Output is deterministic for a given seed. A chosen share of items is defective on
purpose, and a chosen share refers to products the warehouse does not know, so
validation, the quality gate and unknown-product handling can be shown.
"""

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from agpp.shared.database import Pool, connection

LOCATIONS = (
    ("LU-01", "Luxembourg Warehouse", "LU"),
    ("LU-02", "Esch Distribution Centre", "LU"),
    ("BE-01", "Brussels Hub", "BE"),
    ("DE-01", "Trier Depot", "DE"),
)
DIRTY_SHARE = 0.15
UNKNOWN_SUPPLIER = "SUP-999"
RECENT_HOURS = 6

Defect = Callable[[random.Random, list[Any], int, datetime], None]


@dataclass(frozen=True)
class SampleFeed:
    """A generated feed, ready to be served as JSON."""

    snapshot_at: str
    items: list[Any]
    defective_items: int
    unknown_product_items: int


def known_product_ids(pool: Pool) -> list[str]:
    """The products currently in the warehouse (the Supplier Product pipeline owns them)."""
    with connection(pool) as conn:
        rows = conn.execute(
            "SELECT product_id FROM warehouse.dim_product WHERE product_key > 0 ORDER BY product_id"
        ).fetchall()
    return [str(row[0]) for row in rows]


def _set(**fields: Any) -> Defect:
    def apply(_rng: random.Random, items: list[Any], position: int, _snapshot: datetime) -> None:
        item = items[position]
        if isinstance(item, dict):
            item.update(fields)

    return apply


def _reserved_above_on_hand(
    _rng: random.Random, items: list[Any], position: int, _snapshot: datetime
) -> None:
    item = items[position]
    if isinstance(item, dict):
        item["reserved"] = int(item["on_hand"]) + 10


def _updated_after_snapshot(
    _rng: random.Random, items: list[Any], position: int, snapshot_at: datetime
) -> None:
    item = items[position]
    if isinstance(item, dict):
        item["updated_at"] = (snapshot_at + timedelta(hours=2)).isoformat(timespec="seconds")


def _not_an_object(
    _rng: random.Random, items: list[Any], position: int, _snapshot: datetime
) -> None:
    items[position] = "not an object"


def _duplicate_key(
    _rng: random.Random, items: list[Any], position: int, _snapshot: datetime
) -> None:
    item, other = items[position], items[(position + 1) % len(items)]
    if isinstance(item, dict) and isinstance(other, dict):
        item.update(location_code=other["location_code"], product_id=other["product_id"])


# Each defect breaks a different rule: some fail parsing, some the business rules.
DEFECTS: dict[str, Defect] = {
    "negative_on_hand": _set(on_hand=-5),
    "on_hand_text": _set(on_hand="abc"),
    "reserved_above_on_hand": _reserved_above_on_hand,
    "missing_location": _set(location_code=""),
    "bad_product_id": _set(product_id="A-1"),
    "naive_updated_at": _set(updated_at="2026-01-15T09:30:00"),
    "updated_after_snapshot": _updated_after_snapshot,
    "nested_value": _set(on_hand={"value": 1}),
    "not_an_object": _not_an_object,
    "duplicate_key": _duplicate_key,
}


def generate_feed(
    product_ids: Sequence[str],
    *,
    locations: int,
    coverage: float,
    bad_item_ratio: float,
    unknown_product_ratio: float,
    seed: int,
    snapshot_at: datetime,
) -> SampleFeed:
    """Build a feed with one item per location and stocked product.

    ``coverage`` is the share of products each location stocks.
    """
    if not product_ids:
        raise ValueError("product_ids must not be empty")
    if not 1 <= locations <= len(LOCATIONS):
        raise ValueError(f"locations must be between 1 and {len(LOCATIONS)}")
    if not 0 < coverage <= 1:
        raise ValueError("coverage must be greater than 0 and at most 1")
    if not 0 <= bad_item_ratio <= 1:
        raise ValueError("bad_item_ratio must be between 0 and 1")
    if not 0 <= unknown_product_ratio <= 1:
        raise ValueError("unknown_product_ratio must be between 0 and 1")

    rng = random.Random(seed)
    items, unknown = _good_items(
        rng, product_ids, locations, coverage, unknown_product_ratio, snapshot_at
    )
    for item in items:
        if rng.random() < DIRTY_SHARE:
            _make_dirty(item)
    defective = _inject_defects(rng, items, round(len(items) * bad_item_ratio), snapshot_at)
    return SampleFeed(snapshot_at.strftime("%Y-%m-%dT%H:%M:%SZ"), items, defective, unknown)


def _good_items(
    rng: random.Random,
    product_ids: Sequence[str],
    locations: int,
    coverage: float,
    unknown_product_ratio: float,
    snapshot_at: datetime,
) -> tuple[list[Any], int]:
    items: list[Any] = []
    unknown = 0
    for code, name, country in LOCATIONS[:locations]:
        for known_id in product_ids:
            if rng.random() > coverage:
                continue
            product_id = known_id
            if rng.random() < unknown_product_ratio:
                unknown += 1
                product_id = f"{UNKNOWN_SUPPLIER}:UNKNOWN-{unknown:04d}"
            on_hand = rng.randrange(0, 500)
            updated_at = snapshot_at - timedelta(minutes=rng.randrange(1, RECENT_HOURS * 60))
            items.append(
                {
                    "location_code": code,
                    "location_name": name,
                    "location_country": country,
                    "product_id": product_id,
                    "on_hand": on_hand,
                    "reserved": rng.randrange(0, on_hand + 1),
                    "reorder_point": rng.randrange(10, 101),
                    "updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
    return items, unknown


def _make_dirty(item: dict[str, Any]) -> None:
    """Make an item messy but still valid (case, padding)."""
    item["location_code"] = item["location_code"].lower()
    item["location_name"] = f"  {item['location_name']} "
    item["product_id"] = item["product_id"].lower()


def _inject_defects(rng: random.Random, items: list[Any], count: int, snapshot_at: datetime) -> int:
    positions = rng.sample(range(len(items)), k=min(count, len(items)))
    kinds = list(DEFECTS)
    for position in positions:
        DEFECTS[rng.choice(kinds)](rng, items, position, snapshot_at)
    return len(positions)
