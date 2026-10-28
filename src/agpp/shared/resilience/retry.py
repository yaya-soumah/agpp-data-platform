"""Bounded retry with exponential backoff for retryable AGPP errors."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from agpp.shared.exceptions import AgppError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """How many times to try and how long to wait between attempts."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay < 0 or self.max_delay < 0:
            raise ValueError("delays must not be negative")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be at least 1")

    def delay_for(self, attempt: int) -> float:
        """Seconds to wait after the given (1-based) failed attempt."""
        return min(self.initial_delay * self.backoff_factor ** (attempt - 1), self.max_delay)


def call_with_retry[T](
    operation: Callable[[], T],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``operation``, retrying only errors marked ``retryable``.

    Other errors, including non-AGPP exceptions, propagate immediately. The last
    error is re-raised once the attempts are used up. The operation must be
    idempotent.
    """
    attempt = 1
    while True:
        try:
            return operation()
        except AgppError as error:
            if not error.retryable:
                raise
            fields = {"stage": error.stage, "error_context": error.context}
            if attempt >= policy.max_attempts:
                logger.error("Giving up after %d attempts", attempt, extra=fields)
                raise
            delay = policy.delay_for(attempt)
            logger.warning(
                "Attempt %d of %d failed; retrying in %.1fs",
                attempt,
                policy.max_attempts,
                delay,
                extra=fields,
            )
            sleep(delay)
            attempt += 1
