"""Stage-level validation failures.

Rejected records are reported as data by the validators; these errors mean the
stage cannot continue.
"""

from typing import ClassVar

from agpp.shared.exceptions.base import AgppError


class DataValidationError(AgppError):
    """A validation failure that stops the stage."""

    stage: ClassVar[str] = "validation"


class SchemaValidationError(DataValidationError):
    """The input does not match the expected structure (for example missing columns)."""


class QualityThresholdExceededError(DataValidationError):
    """Too many records were rejected for the run to continue."""
