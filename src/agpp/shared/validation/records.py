"""Record-level validation outcomes shared by every pipeline (ADR-0012, ADR-0017)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class RejectionStage(StrEnum):
    """The check that rejected a record."""

    PARSING = "parsing"
    BUSINESS = "business"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class RejectedRecord:
    """A record that failed a check, with every reason found at that check.

    ``source_id`` names the unit the record came from: a supplier, a file.
    """

    source_id: str
    line_number: int
    stage: RejectionStage
    reasons: tuple[str, ...]
    raw: Mapping[str, str]
