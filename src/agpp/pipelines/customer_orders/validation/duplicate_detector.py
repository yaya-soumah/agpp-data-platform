"""Duplicate detection within the order file (ADR-0016)."""

from collections.abc import Sequence

from agpp.pipelines.customer_orders.validation.result import (
    ParsedLine,
    RejectedRecord,
    RejectionStage,
)


def remove_duplicates(
    parsed: Sequence[ParsedLine], *, source_id: str
) -> tuple[list[ParsedLine], list[RejectedRecord]]:
    """Keep one record per ``(order_id, line_number)``: latest ``updated_at``, later line on a tie.

    The original order of the kept records is preserved.
    """
    winners: dict[tuple[str, int], ParsedLine] = {}
    for record in parsed:
        key = (record.line.order_id, record.line.line_number)
        current = winners.get(key)
        if current is None or record.line.updated_at >= current.line.updated_at:
            winners[key] = record

    unique: list[ParsedLine] = []
    rejected: list[RejectedRecord] = []
    for record in parsed:
        winner = winners[(record.line.order_id, record.line.line_number)]
        if winner is record:
            unique.append(record)
            continue
        rejected.append(
            RejectedRecord(
                source_id,
                record.line_number,
                RejectionStage.DUPLICATE,
                (f"order_id: duplicate of line {winner.line_number}, which was kept",),
                record.raw,
            )
        )
    return unique, rejected
