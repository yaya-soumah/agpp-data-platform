"""Configuration-driven business rules (ADR-0012)."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from agpp.pipelines.supplier_product.config import QualityConfig
from agpp.pipelines.supplier_product.validation.result import (
    ParsedRecord,
    RejectedRecord,
    RejectionStage,
)


def validate_business_rules(
    parsed: Sequence[ParsedRecord], quality: QualityConfig, *, now: datetime
) -> tuple[list[ParsedRecord], list[RejectedRecord]]:
    """Check currency, maximum price and timestamp against the limits in ``quality``.

    ``now`` must be timezone-aware. Every violated rule of a record is reported.
    """
    allowed = sorted(quality.allowed_currencies)
    latest_allowed = now + timedelta(minutes=quality.future_tolerance_minutes)

    accepted: list[ParsedRecord] = []
    rejected: list[RejectedRecord] = []
    for record in parsed:
        product = record.product
        reasons: list[str] = []
        if product.currency not in allowed:
            reasons.append(
                f"currency: {product.currency} is not allowed (allowed: {', '.join(allowed)})"
            )
        if product.unit_price > quality.max_unit_price:
            reasons.append(
                f"unit_price: {product.unit_price} exceeds the maximum {quality.max_unit_price}"
            )
        if product.updated_at > latest_allowed:
            reasons.append(f"updated_at: {product.updated_at.isoformat()} is in the future")

        if reasons:
            rejected.append(
                RejectedRecord(
                    product.supplier_id,
                    record.line_number,
                    RejectionStage.BUSINESS,
                    tuple(reasons),
                    record.raw,
                )
            )
        else:
            accepted.append(record)
    return accepted, rejected
