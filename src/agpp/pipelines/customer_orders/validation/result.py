"""Outcome types of the validation stage (ADR-0012, ADR-0016)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from agpp.pipelines.customer_orders.models import OrderLine


class RejectionStage(StrEnum):
    """The check that rejected a record."""

    PARSING = "parsing"
    BUSINESS = "business"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class ParsedLine:
    """A record that passed parsing, still tied to its source line and raw values."""

    line_number: int
    raw: Mapping[str, str]
    line: OrderLine


@dataclass(frozen=True)
class RejectedRecord:
    """A record that failed a check, with every reason found at that check."""

    source_id: str
    line_number: int
    stage: RejectionStage
    reasons: tuple[str, ...]
    raw: Mapping[str, str]


@dataclass(frozen=True)
class ValidationResult:
    """What validation decided about the order file."""

    source_id: str
    rows_read: int
    valid: tuple[OrderLine, ...]
    rejected: tuple[RejectedRecord, ...]
    ignored_columns: tuple[str, ...] = ()

    @property
    def reject_ratio(self) -> float:
        """Share of rows rejected; 0.0 for a file without data rows."""
        return len(self.rejected) / self.rows_read if self.rows_read else 0.0

    def rejected_by(self, stage: RejectionStage) -> int:
        """Number of records rejected by one check."""
        return sum(1 for record in self.rejected if record.stage is stage)
