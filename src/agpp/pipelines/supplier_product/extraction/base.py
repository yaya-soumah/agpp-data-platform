"""The contract shared by every extractor (ADR-0011)."""

from dataclasses import dataclass
from typing import Protocol

from agpp.shared.extraction import RawRecord

__all__ = ["ExtractionResult", "Extractor", "RawRecord"]


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
