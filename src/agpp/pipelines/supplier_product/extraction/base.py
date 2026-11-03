"""The contract shared by every extractor (ADR-0011)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawRecord:
    """One source row exactly as read: text values keyed by column name.

    ``line_number`` points back to the source for reject reports. ``problem`` is
    set when the row is structurally wrong; validation turns it into a rejection.
    """

    line_number: int
    values: Mapping[str, str]
    problem: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    """Everything read from one supplier's source."""

    supplier_id: str
    source: str
    columns: tuple[str, ...]
    records: tuple[RawRecord, ...]

    @property
    def row_count(self) -> int:
        return len(self.records)


class Extractor(Protocol):
    """Reads one supplier's source."""

    def extract(self) -> ExtractionResult: ...
