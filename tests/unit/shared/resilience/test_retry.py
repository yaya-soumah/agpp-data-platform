import logging

import pytest

from agpp.shared.exceptions import (
    AgppError,
    ConfigurationError,
    SourceUnavailableError,
)
from agpp.shared.resilience.retry import RetryPolicy, call_with_retry


class Flaky:
    """Fails ``failures`` times with ``error`` and then succeeds."""

    def __init__(self, failures: int, error: Exception) -> None:
        self.failures = failures
        self.error = error
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return "ok"


def _run(
    operation: Flaky, policy: RetryPolicy | None = None
) -> tuple[str | None, list[float], Exception | None]:
    sleeps: list[float] = []
    try:
        result = call_with_retry(operation, policy or RetryPolicy(), sleep=sleeps.append)
    except (AgppError, ValueError) as error:
        return None, sleeps, error
    return result, sleeps, None


def test_success_needs_no_retry() -> None:
    operation = Flaky(0, SourceUnavailableError("down"))

    result, sleeps, error = _run(operation)

    assert (result, error) == ("ok", None)
    assert operation.calls == 1
    assert sleeps == []


def test_transient_errors_are_retried_with_backoff() -> None:
    operation = Flaky(2, SourceUnavailableError("down"))

    result, sleeps, error = _run(operation)

    assert (result, error) == ("ok", None)
    assert operation.calls == 3
    assert sleeps == [1.0, 2.0]


def test_last_error_is_raised_when_attempts_run_out() -> None:
    boom = SourceUnavailableError("down")
    operation = Flaky(10, boom)

    result, sleeps, error = _run(operation)

    assert result is None
    assert error is boom
    assert operation.calls == 3
    assert sleeps == [1.0, 2.0]


def test_non_retryable_agpp_errors_fail_fast() -> None:
    operation = Flaky(1, ConfigurationError("bad"))

    _, sleeps, error = _run(operation)

    assert isinstance(error, ConfigurationError)
    assert operation.calls == 1
    assert sleeps == []


def test_foreign_exceptions_propagate_immediately() -> None:
    operation = Flaky(1, ValueError("bug"))

    _, sleeps, error = _run(operation)

    assert isinstance(error, ValueError)
    assert operation.calls == 1
    assert sleeps == []


def test_delays_are_capped() -> None:
    policy = RetryPolicy(max_attempts=5, initial_delay=10, backoff_factor=10, max_delay=30)

    assert [policy.delay_for(attempt) for attempt in (1, 2, 3, 4)] == [10, 30, 30, 30]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_delay": -1.0},
        {"backoff_factor": 0.5},
    ],
)
def test_invalid_policies_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        RetryPolicy(**kwargs)  # type: ignore[arg-type]


def test_retries_and_giving_up_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    operation = Flaky(10, SourceUnavailableError("down", context={"source": "api"}))

    with caplog.at_level(logging.WARNING):
        _run(operation)

    assert "Attempt 1 of 3 failed" in caplog.text
    assert "Giving up after 3 attempts" in caplog.text
