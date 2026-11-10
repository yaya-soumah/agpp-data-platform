"""Configuration-driven business rules (ADR-0016)."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from agpp.pipelines.customer_orders.config import QualityConfig
from agpp.pipelines.customer_orders.validation.result import (
    ParsedLine,
    RejectedRecord,
    RejectionStage,
)
from agpp.shared.dates.calendar import FIRST_DATE, LAST_DATE


def validate_business_rules(
    parsed: Sequence[ParsedLine], quality: QualityConfig, *, source_id: str, now: datetime
) -> tuple[list[ParsedLine], list[RejectedRecord]]:
    """Check currency, line amount, timestamps and calendar range.

    ``now`` must be timezone-aware. Every violated rule of a record is reported.
    """
    allowed = sorted(quality.allowed_currencies)
    latest_allowed = now + timedelta(minutes=quality.future_tolerance_minutes)

    accepted: list[ParsedLine] = []
    rejected: list[RejectedRecord] = []
    for record in parsed:
        line = record.line
        reasons: list[str] = []
        if line.currency not in allowed:
            reasons.append(
                f"currency: {line.currency} is not allowed (allowed: {', '.join(allowed)})"
            )
        if line.line_amount > quality.max_line_amount:
            reasons.append(
                f"quantity: line amount {line.line_amount} exceeds the maximum"
                f" {quality.max_line_amount}"
            )
        if line.ordered_at > latest_allowed:
            reasons.append(f"ordered_at: {line.ordered_at.isoformat()} is in the future")
        if line.updated_at > latest_allowed:
            reasons.append(f"updated_at: {line.updated_at.isoformat()} is in the future")
        if line.updated_at < line.ordered_at:
            reasons.append("updated_at: is before ordered_at")
        if not FIRST_DATE <= line.ordered_at.date() <= LAST_DATE:
            reasons.append(
                f"ordered_at: outside the supported calendar ({FIRST_DATE.year}-{LAST_DATE.year})"
            )

        if reasons:
            rejected.append(
                RejectedRecord(
                    source_id,
                    record.line_number,
                    RejectionStage.BUSINESS,
                    tuple(reasons),
                    record.raw,
                )
            )
        else:
            accepted.append(record)
    return accepted, rejected
