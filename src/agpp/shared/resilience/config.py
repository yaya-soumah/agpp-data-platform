"""Retry settings shared by every pipeline's configuration (ADR-0017)."""

from pydantic import Field

from agpp.shared.models import AgppModel
from agpp.shared.resilience.retry import RetryPolicy


class RetryConfig(AgppModel):
    """How hard to try before an operation counts as failed."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=1.0, ge=0)

    def policy(self) -> RetryPolicy:
        """The retry policy these settings describe."""
        return RetryPolicy(max_attempts=self.max_attempts, initial_delay=self.initial_delay_seconds)
