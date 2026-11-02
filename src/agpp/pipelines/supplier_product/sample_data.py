"""Synthetic supplier catalogs for development and demos (ADR-0010).

Output is deterministic for a given seed. A chosen share of rows is
defective on purpose, so validation and the quality gate can be demonstrated.
"""

import csv
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from agpp.pipelines.supplier_product.config import SupplierConfig, SupplierProductConfig

COLUMNS = (
    "supplier_sku",
    "product_name",
    "category",
    "unit_price",
    "currency",
    "min_order_quantity",
    "lead_time_days",
    "is_active",
    "updated_at",
)

CATALOG = {
    "Hex Bolt": "Fasteners",
    "Washer": "Fasteners",
    "Wall Bracket": "Hardware",
    "Cable Tie": "Electrical",
    "LED Panel": "Electrical",
    "Safety Gloves": "Safety",
    "Ball Bearing": "Mechanical",
    "Copy Paper": "Office",
    "Stapler": "Office",
    "Toner Cartridge": "Office",
}
VARIANTS = ("M6", "M8", "M10", "Small", "Large", "Pro")
DIRTY_SHARE = 0.15
RECENT_DAYS = 30

Row = dict[str, str]
Defect = Callable[[random.Random, list[Row], int, datetime], None]


@dataclass(frozen=True)
class GenerationSummary:
    """What was written for one supplier."""

    supplier_id: str
    path: Path
    rows: int
    defective_rows: int


def _set(field: str, value: str) -> Defect:
    def apply(_rng: random.Random, rows: list[Row], position: int, _now: datetime) -> None:
        rows[position][field] = value

    return apply


def _future_timestamp(_rng: random.Random, rows: list[Row], position: int, now: datetime) -> None:
    rows[position]["updated_at"] = (now + timedelta(days=2)).isoformat(timespec="seconds")


def _duplicate_sku(_rng: random.Random, rows: list[Row], position: int, _now: datetime) -> None:
    rows[position]["supplier_sku"] = rows[(position + 1) % len(rows)]["supplier_sku"]


# Each defect breaks a different rule: some fail parsing, some fail business rules.
DEFECTS: dict[str, Defect] = {
    "missing_sku": _set("supplier_sku", ""),
    "zero_price": _set("unit_price", "0.00"),
    "negative_price": _set("unit_price", "-4.50"),
    "too_many_decimals": _set("unit_price", "3.14159"),
    "price_not_a_number": _set("unit_price", "N/A"),
    "price_above_maximum": _set("unit_price", "9999999.00"),
    "bad_currency_format": _set("currency", "EURO"),
    "unsupported_currency": _set("currency", "JPY"),
    "lead_time_out_of_range": _set("lead_time_days", "999"),
    "naive_timestamp": _set("updated_at", "2026-01-15T09:30:00"),
    "future_timestamp": _future_timestamp,
    "duplicate_sku": _duplicate_sku,
}


def generate_supplier_files(
    config: SupplierProductConfig,
    *,
    rows_per_supplier: int,
    bad_row_ratio: float,
    seed: int,
    now: datetime,
) -> list[GenerationSummary]:
    """Write one CSV per configured supplier, at its configured path and format."""
    if rows_per_supplier < 1:
        raise ValueError("rows_per_supplier must be at least 1")
    if not 0 <= bad_row_ratio <= 1:
        raise ValueError("bad_row_ratio must be between 0 and 1")

    summaries: list[GenerationSummary] = []
    for number, supplier in enumerate(config.suppliers, start=1):
        rng = random.Random(seed * 1000 + number)
        rows = [
            _good_row(rng, number, sequence, now, config.quality.allowed_currencies)
            for sequence in range(rows_per_supplier)
        ]
        for row in rows:
            if rng.random() < DIRTY_SHARE:
                _make_dirty(row)
        defective = _inject_defects(rng, rows, round(rows_per_supplier * bad_row_ratio), now)
        path = _write_csv(supplier, rows)
        summaries.append(GenerationSummary(supplier.supplier_id, path, len(rows), defective))
    return summaries


def _good_row(
    rng: random.Random,
    supplier_number: int,
    sequence: int,
    now: datetime,
    currencies: tuple[str, ...],
) -> Row:
    noun = rng.choice(list(CATALOG))
    price = Decimal(rng.randrange(50, 50_000)) / 100
    currency = currencies[0] if rng.random() > 0.1 else rng.choice(currencies)
    updated = now - timedelta(minutes=rng.randrange(0, RECENT_DAYS * 24 * 60))
    stamp = (
        updated.strftime("%Y-%m-%dT%H:%M:%SZ")
        if sequence % 2 == 0
        else updated.isoformat(timespec="seconds")
    )
    return {
        "supplier_sku": f"S{supplier_number}-{sequence:05d}",
        "product_name": f"{noun} {rng.choice(VARIANTS)}",
        "category": CATALOG[noun],
        "unit_price": f"{price:.2f}",
        "currency": currency,
        "min_order_quantity": str(rng.choice((1, 5, 10, 25, 50))),
        "lead_time_days": str(rng.randrange(1, 45)),
        "is_active": "true" if rng.random() > 0.1 else "false",
        "updated_at": stamp,
    }


def _make_dirty(row: Row) -> None:
    """Make a row messy but still valid (padding, lower case)."""
    row["supplier_sku"] = f"  {row['supplier_sku'].lower()} "
    row["product_name"] = f" {row['product_name']}  "
    row["currency"] = row["currency"].lower()


def _inject_defects(rng: random.Random, rows: list[Row], count: int, now: datetime) -> int:
    positions = rng.sample(range(len(rows)), k=min(count, len(rows)))
    kinds = list(DEFECTS)
    for position in positions:
        DEFECTS[rng.choice(kinds)](rng, rows, position, now)
    return len(positions)


def _write_csv(supplier: SupplierConfig, rows: list[Row]) -> Path:
    path = Path(supplier.source.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=supplier.source.encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter=supplier.source.delimiter)
        writer.writeheader()
        writer.writerows(rows)
    return path
