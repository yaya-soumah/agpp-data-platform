"""Business rules for stock items (ADR-0018)."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from agpp.pipelines.inventory.config import QualityConfig
from agpp.pipelines.inventory.validation.result import (
    ParsedItem,
    RejectedRecord,
    RejectionStage,
)


def validate_business_rules(
    parsed: Sequence[ParsedItem],
    quality: QualityConfig,
    *,
    source_id: str,
    snapshot_at: datetime,
) -> tuple[list[ParsedItem], list[RejectedRecord]]:
    """Check that reserved stock fits on hand and that no item is newer than the snapshot.

    Every violated rule of an item is reported.
    """
    latest_allowed = snapshot_at + timedelta(minutes=quality.future_tolerance_minutes)

    accepted: list[ParsedItem] = []
    rejected: list[RejectedRecord] = []
    for record in parsed:
        item = record.item
        reasons: list[str] = []
        if item.reserved > item.on_hand:
            reasons.append(f"reserved: {item.reserved} exceeds on_hand {item.on_hand}")
        if item.updated_at > latest_allowed:
            reasons.append(f"updated_at: {item.updated_at.isoformat()} is after the snapshot")

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
