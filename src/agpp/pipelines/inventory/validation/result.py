"""Outcome types of the validation stage (ADR-0012, ADR-0018)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from agpp.pipelines.inventory.models import InventoryItem
from agpp.shared.validation import RejectedRecord, RejectionStage

__all__ = ["ParsedItem", "RejectedRecord", "RejectionStage", "ValidationResult"]


@dataclass(frozen=True)
class ParsedItem:
    """An item that passed parsing, still tied to its feed position and raw values."""

    line_number: int
    raw: Mapping[str, str]
    item: InventoryItem


@dataclass(frozen=True)
class ValidationResult:
    """What validation decided about the feed."""

    source_id: str
    snapshot_at: datetime
    rows_read: int
    valid: tuple[InventoryItem, ...]
    rejected: tuple[RejectedRecord, ...]
    ignored_columns: tuple[str, ...] = ()

    @property
    def reject_ratio(self) -> float:
        """Share of items rejected; 0.0 for an empty feed."""
        return len(self.rejected) / self.rows_read if self.rows_read else 0.0

    def rejected_by(self, stage: RejectionStage) -> int:
        """Number of items rejected by one check."""
        return sum(1 for record in self.rejected if record.stage is stage)
