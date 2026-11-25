import pytest
from pydantic import ValidationError

from agpp.shared.quality import QualityCheck, QualityConfig


def _check(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "share_of_x",
        "description": "Share of x",
        "sql": "SELECT 1",
        "warn": 0.1,
        "fail": 0.2,
    }
    return {**base, **overrides}


def test_a_check_is_a_maximum_by_default() -> None:
    assert QualityCheck.model_validate(_check()).comparison == "max"


@pytest.mark.parametrize("name", ["", "Share", "1share", "share-x", "share x"])
def test_names_must_be_snake_case(name: str) -> None:
    with pytest.raises(ValidationError):
        QualityCheck.model_validate(_check(name=name))


def test_a_maximum_needs_warn_not_above_fail() -> None:
    with pytest.raises(ValidationError, match="warn must not be above fail"):
        QualityCheck.model_validate(_check(warn=0.3, fail=0.2))


def test_a_minimum_needs_warn_not_below_fail() -> None:
    with pytest.raises(ValidationError, match="warn must not be below fail"):
        QualityCheck.model_validate(_check(comparison="min", warn=5.0, fail=10.0))

    assert QualityCheck.model_validate(_check(comparison="min", warn=10.0, fail=5.0))


def test_equal_thresholds_are_allowed() -> None:
    assert QualityCheck.model_validate(_check(warn=0.0, fail=0.0))


def test_an_unknown_comparison_is_rejected() -> None:
    with pytest.raises(ValidationError):
        QualityCheck.model_validate(_check(comparison="avg"))


def test_a_config_needs_at_least_one_check() -> None:
    with pytest.raises(ValidationError):
        QualityConfig.model_validate({"checks": []})


def test_check_names_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="duplicate check names: share_of_x"):
        QualityConfig.model_validate({"checks": [_check(), _check()]})
