"""Errors raised while extracting data from a source."""

from typing import ClassVar

from agpp.shared.exceptions.base import AgppError


class ExtractionError(AgppError):
    """Data could not be read from a source."""

    stage: ClassVar[str] = "extraction"


class SourceUnavailableError(ExtractionError):
    """The source could not be reached (network, timeout, server error)."""

    retryable: ClassVar[bool] = True


class UnsupportedSourceError(ExtractionError):
    """The requested source type has no extractor."""
