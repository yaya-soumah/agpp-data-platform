"""Duplicate detection within the feed (ADR-0018)."""

from collections.abc import Sequence

from agpp.pipelines.inventory.validation.result import (
    ParsedItem,
    RejectedRecord,
    RejectionStage,
)


def remove_duplicates(
    parsed: Sequence[ParsedItem], *, source_id: str
) -> tuple[list[ParsedItem], list[RejectedRecord]]:
    """Keep one item per ``(location_code, product_id)``: latest ``updated_at``,
    later item on a tie.

    The original order of the kept items is preserved.
    """
    winners: dict[tuple[str, str], ParsedItem] = {}
    for record in parsed:
        key = (record.item.location_code, record.item.product_id)
        current = winners.get(key)
        if current is None or record.item.updated_at >= current.item.updated_at:
            winners[key] = record

    unique: list[ParsedItem] = []
    rejected: list[RejectedRecord] = []
    for record in parsed:
        winner = winners[(record.item.location_code, record.item.product_id)]
        if winner is record:
            unique.append(record)
            continue
        rejected.append(
            RejectedRecord(
                source_id,
                record.line_number,
                RejectionStage.DUPLICATE,
                (f"location_code: duplicate of item {winner.line_number}, which was kept",),
                record.raw,
            )
        )
    return unique, rejected
