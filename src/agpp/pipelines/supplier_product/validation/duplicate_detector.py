"""Duplicate detection within one supplier file (ADR-0012)."""

from collections.abc import Sequence

from agpp.pipelines.supplier_product.validation.result import (
    ParsedRecord,
    RejectedRecord,
    RejectionStage,
)


def remove_duplicates(
    parsed: Sequence[ParsedRecord],
) -> tuple[list[ParsedRecord], list[RejectedRecord]]:
    """Keep one record per ``supplier_sku``: the latest ``updated_at``, later line on a tie.

    Records are expected to be normalized, so ``" ab-1"`` and ``"AB-1"`` clash.
    The original order of the kept records is preserved.
    """
    winners: dict[tuple[str, str], ParsedRecord] = {}
    for record in parsed:
        key = (record.product.supplier_id, record.product.supplier_sku)
        current = winners.get(key)
        if current is None or record.product.updated_at >= current.product.updated_at:
            winners[key] = record

    unique: list[ParsedRecord] = []
    rejected: list[RejectedRecord] = []
    for record in parsed:
        winner = winners[(record.product.supplier_id, record.product.supplier_sku)]
        if winner is record:
            unique.append(record)
            continue
        rejected.append(
            RejectedRecord(
                record.product.supplier_id,
                record.line_number,
                RejectionStage.DUPLICATE,
                (f"supplier_sku: duplicate of line {winner.line_number}, which was kept",),
                record.raw,
            )
        )
    return unique, rejected
