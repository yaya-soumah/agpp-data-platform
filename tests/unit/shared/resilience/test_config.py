import pytest
from pydantic import ValidationError

from agpp.shared.resilience.config import RetryConfig
from agpp.shared.resilience.retry import RetryPolicy


def test_defaults() -> None:
    config = RetryConfig()

    assert (config.max_attempts, config.initial_delay_seconds) == (3, 1.0)


def test_the_settings_describe_a_retry_policy() -> None:
    policy = RetryConfig(max_attempts=5, initial_delay_seconds=0.5).policy()

    assert policy == RetryPolicy(max_attempts=5, initial_delay=0.5)


@pytest.mark.parametrize(
    "values",
    [{"max_attempts": 0}, {"max_attempts": 11}, {"initial_delay_seconds": -1}],
)
def test_out_of_range_settings_are_rejected(values: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        RetryConfig.model_validate(values)
