"""Synthetic order lines for development and demos (ADR-0016).

Output is deterministic for a given seed. A chosen share of rows is defective on
purpose, and a chosen share of lines refers to products the warehouse does not
know, so validation, the quality gate and unknown-product handling can be shown.
"""

import csv
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.validation.schema import REQUIRED_COLUMNS
from agpp.shared.database import Pool, connection

CUSTOMER_NAMES = (
    "Dupont Industries",
    "Weber & Fils",
    "Schmit Logistics",
    "Hoffmann Retail",
    "Martin Services",
    "Klein Technik",
    "Faber Bureau",
    "Reuter Handel",
    "Meyer Atelier",
    "Thill Construction",
)
COUNTRIES = ("LU", "BE", "DE", "FR", "NL")
STATUSES = ("placed", "shipped", "delivered", "cancelled")
STATUS_WEIGHTS = (3, 3, 5, 1)
RECENT_DAYS = 30
DIRTY_SHARE = 0.15
UNKNOWN_SUPPLIER = "SUP-999"

Row = dict[str, str]
Defect = Callable[[random.Random, list[Row], int, datetime], None]


@dataclass(frozen=True)
class GenerationSummary:
    """What was written."""

    path: Path
    rows: int
    defective_rows: int
    unknown_product_lines: int


def known_product_ids(pool: Pool) -> list[str]:
    """The products currently in the warehouse (the Supplier Product pipeline owns them)."""
    with connection(pool) as conn:
        rows = conn.execute(
            "SELECT product_id FROM warehouse.dim_product WHERE product_key > 0 ORDER BY product_id"
        ).fetchall()
    return [str(row[0]) for row in rows]


def _set(**fields: str) -> Defect:
    def apply(_rng: random.Random, rows: list[Row], position: int, _now: datetime) -> None:
        rows[position].update(fields)

    return apply


def _future_order(_rng: random.Random, rows: list[Row], position: int, now: datetime) -> None:
    stamp = (now + timedelta(days=2)).isoformat(timespec="seconds")
    rows[position].update(ordered_at=stamp, updated_at=stamp)


def _duplicate_key(_rng: random.Random, rows: list[Row], position: int, _now: datetime) -> None:
    other = rows[(position + 1) % len(rows)]
    rows[position].update(order_id=other["order_id"], line_number=other["line_number"])


# Each defect breaks a different rule: some fail parsing, some the business rules.
DEFECTS: dict[str, Defect] = {
    "missing_customer": _set(customer_id=""),
    "zero_quantity": _set(quantity="0"),
    "quantity_not_a_number": _set(quantity="abc"),
    "negative_price": _set(unit_price="-3.50"),
    "too_many_decimals": _set(unit_price="1.23456"),
    "bad_currency_format": _set(currency="EURO"),
    "unknown_status": _set(status="lost"),
    "naive_ordered_at": _set(ordered_at="2026-01-15T09:30:00"),
    "malformed_product_id": _set(product_id="A-1"),
    "unsupported_currency": _set(currency="JPY"),
    "amount_above_maximum": _set(quantity="10000", unit_price="999999.00"),
    "future_order": _future_order,
    "update_before_order": _set(updated_at="2000-01-02T00:00:00Z"),
    "outside_calendar": _set(ordered_at="1999-12-31T10:00:00Z"),
    "duplicate_key": _duplicate_key,
}


def generate_orders_file(
    config: CustomerOrdersConfig,
    *,
    product_ids: Sequence[str],
    lines: int,
    bad_row_ratio: float,
    unknown_product_ratio: float,
    seed: int,
    now: datetime,
) -> GenerationSummary:
    """Write the order file at the configured path, delimiter and encoding."""
    if lines < 1:
        raise ValueError("lines must be at least 1")
    if not 0 <= bad_row_ratio <= 1:
        raise ValueError("bad_row_ratio must be between 0 and 1")
    if not 0 <= unknown_product_ratio <= 1:
        raise ValueError("unknown_product_ratio must be between 0 and 1")
    if not product_ids and unknown_product_ratio < 1:
        raise ValueError("product_ids must not be empty unless unknown_product_ratio is 1")

    rng = random.Random(seed)
    rows, unknown = _good_rows(rng, config, product_ids, lines, unknown_product_ratio, now)
    for row in rows:
        if rng.random() < DIRTY_SHARE:
            _make_dirty(row)
    defective = _inject_defects(rng, rows, round(lines * bad_row_ratio), now)
    path = _write_csv(config, rows)
    return GenerationSummary(path, len(rows), defective, unknown)


def _good_rows(
    rng: random.Random,
    config: CustomerOrdersConfig,
    product_ids: Sequence[str],
    lines: int,
    unknown_product_ratio: float,
    now: datetime,
) -> tuple[list[Row], int]:
    customers = [
        (f"CUS-{number:05d}", rng.choice(CUSTOMER_NAMES), rng.choice(COUNTRIES))
        for number in range(1, max(5, lines // 6) + 1)
    ]
    currencies = config.quality.allowed_currencies
    rows: list[Row] = []
    unknown = 0
    order_number = 0
    while len(rows) < lines:
        order_number += 1
        customer_id, customer_name, country = rng.choice(customers)
        ordered_at = now - timedelta(minutes=rng.randrange(60, RECENT_DAYS * 24 * 60))
        currency = currencies[0] if rng.random() > 0.1 else rng.choice(currencies)
        for line_number in range(1, rng.randrange(1, 5) + 1):
            if len(rows) == lines:
                break
            if rng.random() < unknown_product_ratio:
                product_id = f"{UNKNOWN_SUPPLIER}:UNKNOWN-{rng.randrange(1, 10_000):04d}"
                unknown += 1
            else:
                product_id = rng.choice(product_ids)
            updated_at = min(now, ordered_at + timedelta(minutes=rng.randrange(0, 3 * 24 * 60)))
            rows.append(
                {
                    "order_id": f"O-{order_number:06d}",
                    "line_number": str(line_number),
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "customer_country": country,
                    "ordered_at": _stamp(ordered_at, len(rows)),
                    "product_id": product_id,
                    "quantity": str(rng.randrange(1, 21)),
                    "unit_price": f"{Decimal(rng.randrange(100, 30_000)) / 100:.2f}",
                    "currency": currency,
                    "status": rng.choices(STATUSES, STATUS_WEIGHTS)[0],
                    "updated_at": _stamp(updated_at, len(rows) + 1),
                }
            )
    return rows, unknown


def _stamp(value: datetime, variant: int) -> str:
    if variant % 2 == 0:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return value.isoformat(timespec="seconds")


def _make_dirty(row: Row) -> None:
    """Make a row messy but still valid (padding, case)."""
    row["customer_id"] = row["customer_id"].lower()
    row["customer_name"] = f"  {row['customer_name']} "
    row["product_id"] = row["product_id"].lower()
    row["currency"] = row["currency"].lower()
    row["status"] = f" {row['status'].title()} "


def _inject_defects(rng: random.Random, rows: list[Row], count: int, now: datetime) -> int:
    positions = rng.sample(range(len(rows)), k=min(count, len(rows)))
    kinds = list(DEFECTS)
    for position in positions:
        DEFECTS[rng.choice(kinds)](rng, rows, position, now)
    return len(positions)


def _write_csv(config: CustomerOrdersConfig, rows: list[Row]) -> Path:
    source = config.source
    path = Path(source.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=source.encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS, delimiter=source.delimiter)
        writer.writeheader()
        writer.writerows(rows)
    return path
