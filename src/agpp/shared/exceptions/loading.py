"""Errors raised while loading data into storage."""

from typing import ClassVar

from agpp.shared.exceptions.base import AgppError


class LoadingError(AgppError):
    """Data could not be loaded."""

    stage: ClassVar[str] = "loading"


class WarehouseWriteError(LoadingError):
    """A write to the analytical warehouse failed."""
