"""Data-quality check definitions (ADR-0020)."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from agpp.shared.models import AgppModel

Comparison = Literal["max", "min"]


class CheckStatus(StrEnum):
    """The outcome of one check."""

    PASS = "pass"  # noqa: S105
    WARN = "warn"
    FAIL = "fail"
    NO_DATA = "no_data"
    ERROR = "error"


class QualityCheck(AgppModel):
    """One check: a read-only query returning one number, and its thresholds.

    With ``max`` the value must not exceed the thresholds; with ``min`` it must not
    fall below them. Past ``warn`` the check warns, past ``fail`` it fails.
    """

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    sql: str = Field(min_length=1)
    comparison: Comparison = "max"
    warn: float
    fail: float

    @model_validator(mode="after")
    def _thresholds_are_ordered(self) -> Self:
        if self.comparison == "max" and self.warn > self.fail:
            raise ValueError("for a maximum, warn must not be above fail")
        if self.comparison == "min" and self.warn < self.fail:
            raise ValueError("for a minimum, warn must not be below fail")
        return self


class QualityConfig(AgppModel):
    """The checks to run."""

    checks: list[QualityCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def _names_are_unique(self) -> Self:
        names = [check.name for check in self.checks]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate check names: {', '.join(duplicates)}")
        return self
