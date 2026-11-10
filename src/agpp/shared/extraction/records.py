"""The raw record shape every extractor produces (ADR-0011, ADR-0017)."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RawRecord:
    """One source row exactly as read: text values keyed by column name.

    ``line_number`` points back to the source for reject reports. ``problem`` is
    set when the row is structurally wrong; validation turns it into a rejection.
    """

    line_number: int
    values: Mapping[str, str]
    problem: str | None = None
