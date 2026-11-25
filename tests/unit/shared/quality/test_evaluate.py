import pytest

from agpp.shared.quality import CheckStatus, QualityCheck, evaluate


def _check(comparison: str, warn: float, fail: float) -> QualityCheck:
    return QualityCheck.model_validate(
        {
            "name": "a_check",
            "description": "d",
            "sql": "SELECT 1",
            "comparison": comparison,
            "warn": warn,
            "fail": fail,
        }
    )


@pytest.mark.parametrize(
    ("comparison", "warn", "fail", "value", "expected"),
    [
        ("max", 0.1, 0.2, 0.05, CheckStatus.PASS),
        ("max", 0.1, 0.2, 0.1, CheckStatus.PASS),
        ("max", 0.1, 0.2, 0.15, CheckStatus.WARN),
        ("max", 0.1, 0.2, 0.2, CheckStatus.WARN),
        ("max", 0.1, 0.2, 0.25, CheckStatus.FAIL),
        ("min", 10.0, 5.0, 12.0, CheckStatus.PASS),
        ("min", 10.0, 5.0, 10.0, CheckStatus.PASS),
        ("min", 10.0, 5.0, 7.0, CheckStatus.WARN),
        ("min", 10.0, 5.0, 5.0, CheckStatus.WARN),
        ("min", 10.0, 5.0, 4.0, CheckStatus.FAIL),
        ("max", 0.0, 0.0, 0.0, CheckStatus.PASS),
        ("max", 0.0, 0.0, 1.0, CheckStatus.FAIL),
    ],
)
def test_a_value_is_compared_with_the_thresholds(
    comparison: str, warn: float, fail: float, value: float, expected: CheckStatus
) -> None:
    assert evaluate(_check(comparison, warn, fail), value) is expected


def test_no_value_means_no_data() -> None:
    assert evaluate(_check("max", 0.1, 0.2), None) is CheckStatus.NO_DATA
