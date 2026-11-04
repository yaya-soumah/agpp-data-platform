from decimal import Decimal

import pytest

from agpp.pipelines.supplier_product.config import QualityConfig
from agpp.pipelines.supplier_product.validation.quality_gate import check_quality
from agpp.pipelines.supplier_product.validation.result import (
    RejectedRecord,
    RejectionStage,
    ValidationResult,
)
from agpp.shared.exceptions import QualityThresholdExceededError

QUALITY = QualityConfig(
    max_reject_ratio=0.10,
    allowed_currencies=("EUR",),
    max_unit_price=Decimal("1000"),
    future_tolerance_minutes=5,
)


def _result(rows_read: int, rejected_count: int) -> ValidationResult:
    rejected = tuple(
        RejectedRecord("SUP-001", line, RejectionStage.PARSING, ("bad",), {})
        for line in range(rejected_count)
    )
    return ValidationResult("SUP-001", rows_read, (), rejected)


def test_a_clean_file_passes() -> None:
    check_quality(_result(100, 0), QUALITY)


def test_a_ratio_equal_to_the_limit_passes() -> None:
    check_quality(_result(100, 10), QUALITY)


def test_a_ratio_above_the_limit_fails_with_context() -> None:
    with pytest.raises(QualityThresholdExceededError) as info:
        check_quality(_result(100, 11), QUALITY)

    assert info.value.context == {
        "supplier_id": "SUP-001",
        "rows_read": 100,
        "rejected": 11,
        "reject_ratio": 0.11,
        "max_reject_ratio": 0.10,
    }
    assert "11 of 100 rows rejected" in str(info.value)
    assert info.value.retryable is False


def test_a_file_without_data_rows_passes() -> None:
    check_quality(_result(0, 0), QUALITY)
