from datetime import UTC, datetime

import pytest

from agpp.pipelines.inventory.config import QualityConfig
from agpp.pipelines.inventory.validation.quality_gate import check_quality
from agpp.pipelines.inventory.validation.result import (
    RejectedRecord,
    RejectionStage,
    ValidationResult,
)
from agpp.shared.exceptions import QualityThresholdExceededError

QUALITY = QualityConfig(
    max_reject_ratio=0.05, max_snapshot_age_hours=26, future_tolerance_minutes=5
)


def _result(rows_read: int, rejected_count: int) -> ValidationResult:
    rejected = tuple(
        RejectedRecord("feed", position, RejectionStage.PARSING, ("bad",), {})
        for position in range(rejected_count)
    )
    snapshot = datetime(2026, 11, 13, 6, 0, tzinfo=UTC)
    return ValidationResult("feed", snapshot, rows_read, (), rejected)


def test_a_clean_feed_passes() -> None:
    check_quality(_result(100, 0), QUALITY)


def test_a_ratio_equal_to_the_limit_passes() -> None:
    check_quality(_result(100, 5), QUALITY)


def test_a_ratio_above_the_limit_fails_with_context() -> None:
    with pytest.raises(QualityThresholdExceededError) as info:
        check_quality(_result(100, 6), QUALITY)

    assert info.value.context == {
        "source": "feed",
        "rows_read": 100,
        "rejected": 6,
        "reject_ratio": 0.06,
        "max_reject_ratio": 0.05,
    }
    assert "6 of 100 items rejected" in str(info.value)


def test_an_empty_feed_passes() -> None:
    check_quality(_result(0, 0), QUALITY)
