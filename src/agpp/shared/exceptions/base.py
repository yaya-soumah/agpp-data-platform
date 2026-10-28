"""Base exception for the AGPP platform."""

from collections.abc import Mapping
from typing import ClassVar


class AgppError(Exception):
    """Root of every error raised by AGPP code.

    ``stage`` classifies the error (used in logs and metrics), ``retryable``
    says whether repeating the operation may succeed, and ``context`` holds
    small diagnostic facts (never secrets or whole records).
    """

    stage: ClassVar[str] = "platform"
    retryable: ClassVar[bool] = False

    def __init__(self, message: str, *, context: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, object] = dict(context or {})
