from decimal import Decimal

import pytest

from agpp.pipelines.customer_orders.config import QualityConfig
from agpp.pipelines.customer_orders.validation.quality_gate import check_quality
from agpp.pipelines.customer_orders.validation.result import (
    RejectedRecord,
    RejectionStage,
    ValidationResult,
)
from agpp.shared.exceptions import QualityThresholdExceededError

QUALITY = QualityConfig(
    max_reject_ratio=0.05,
    allowed_currencies=("EUR",),
    max_line_amount=Decimal("1000"),
    future_tolerance_minutes=5,
)


def _result(rows_read: int, rejected_count: int) -> ValidationResult:
    rejected = tuple(
        RejectedRecord("orders.csv", line, RejectionStage.PARSING, ("bad",), {})
        for line in range(rejected_count)
    )
    return ValidationResult("orders.csv", rows_read, (), rejected)


def test_a_clean_file_passes() -> None:
    check_quality(_result(100, 0), QUALITY)


def test_a_ratio_equal_to_the_limit_passes() -> None:
    check_quality(_result(100, 5), QUALITY)


def test_a_ratio_above_the_limit_fails_with_context() -> None:
    with pytest.raises(QualityThresholdExceededError) as info:
        check_quality(_result(100, 6), QUALITY)

    assert info.value.context == {
        "source": "orders.csv",
        "rows_read": 100,
        "rejected": 6,
        "reject_ratio": 0.06,
        "max_reject_ratio": 0.05,
    }
    assert "6 of 100 rows rejected" in str(info.value)


def test_a_file_without_data_rows_passes() -> None:
    check_quality(_result(0, 0), QUALITY)
