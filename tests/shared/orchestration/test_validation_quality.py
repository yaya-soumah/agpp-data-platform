from decimal import Decimal

import pytest
from src.shared.exceptions import ValidationError
from src.shared.orchestration.validation_quality import ValidationQualityPolicy


def test_accepts_rejection_ratio_below_threshold() -> None:
    policy = ValidationQualityPolicy(Decimal("0.20"))

    result = policy.evaluate(
        records_extracted=1000,
        records_valid=850,
        records_rejected=150,
    )

    assert result.records_extracted == 1000
    assert result.records_valid == 850
    assert result.records_rejected == 150
    assert result.rejection_ratio == Decimal("0.15")


def test_rejects_rejection_ratio_above_threshold() -> None:
    policy = ValidationQualityPolicy(Decimal("0.20"))

    with pytest.raises(ValidationError) as exc_info:
        policy.evaluate(
            records_extracted=100,
            records_valid=79,
            records_rejected=21,
        )
    assert exc_info.value.error_code == "VALIDATION_REJECTION_THRESHOLD_EXCEEDED"

    assert exc_info.value.retryable is False


def test_accepts_zero_extracted_records() -> None:
    policy = ValidationQualityPolicy(Decimal("0.20"))

    result = policy.evaluate(
        records_extracted=0,
        records_valid=0,
        records_rejected=0,
    )

    assert result.records_extracted == 0
    assert result.records_valid == 0
    assert result.records_rejected == 0
    assert result.rejection_ratio == Decimal("0")


@pytest.mark.parametrize(
    "extracted,valid,rejected",
    [
        (-1, 0, 0),
        (10, -1, 11),
        (10, 11, -1),
    ],
)
def test_rejects_negative_counts(
    extracted: int,
    valid: int,
    rejected: int,
) -> None:
    policy = ValidationQualityPolicy(Decimal("0.20"))

    with pytest.raises(ValueError):
        policy.evaluate(
            records_extracted=extracted,
            records_valid=valid,
            records_rejected=rejected,
        )


def test_rejects_inconsistent_counts() -> None:
    policy = ValidationQualityPolicy(Decimal("0.20"))

    with pytest.raises(ValueError):
        policy.evaluate(
            records_extracted=100,
            records_valid=80,
            records_rejected=10,
        )


@pytest.mark.parametrize(
    "threshold",
    [
        Decimal("-0.01"),
        Decimal("1.01"),
    ],
)
def test_rejects_invalid_threshold(threshold: Decimal) -> None:
    with pytest.raises(ValidationError):
        ValidationQualityPolicy(threshold)
