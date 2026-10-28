"""Errors raised while transforming validated data."""

from typing import ClassVar

from agpp.shared.exceptions.base import AgppError


class TransformationError(AgppError):
    """Validated data could not be transformed."""

    stage: ClassVar[str] = "transformation"
