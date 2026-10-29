"""Errors raised by external dependencies such as the database or network."""

from typing import ClassVar

from agpp.shared.exceptions.base import AgppError


class InfrastructureError(AgppError):
    """An external dependency failed."""

    stage: ClassVar[str] = "infrastructure"


class TransientInfrastructureError(InfrastructureError):
    """A failure that may disappear if the operation is repeated."""

    retryable: ClassVar[bool] = True


class DatabaseConnectionError(TransientInfrastructureError):
    """The database could not be reached."""


class MigrationError(InfrastructureError):
    """A migration is invalid, was modified after being applied, or is inconsistent."""
