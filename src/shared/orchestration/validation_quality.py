from dataclasses import dataclass
from decimal import Decimal

from src.shared.exceptions import ValidationError


@dataclass(frozen=True)
class ValidationQualityResult:
    """Result of a validation quality evaluation."""

    records_extracted: int
    records_valid: int
    records_rejected: int
    rejection_ratio: Decimal


class ValidationQualityPolicy:
    """Evaluates whether validation results meet pipeline quality requirements."""

    def __init__(self, max_rejection_ratio: Decimal) -> None:
        if not Decimal("0") <= max_rejection_ratio <= Decimal("1"):
            raise ValidationError(
                "max_rejection_ratio must be between 0 and 1.",
                error_code="VALIDATION_INVALID_DATA_QUALITY_RATIO",
            )
        self._max_rejection_ratio = max_rejection_ratio

    def evaluate(
        self,
        *,
        records_extracted: int,
        records_valid: int,
        records_rejected: int,
    ) -> ValidationQualityResult:
        if records_extracted < 0:
            raise ValueError("records_extracted must not be negative.")

        if records_valid < 0:
            raise ValueError("records_valid must not be negative.")

        if records_rejected < 0:
            raise ValueError("records_rejected must not be negative.")

        if records_valid + records_rejected != records_extracted:
            raise ValueError(
                "records_valid and records_rejected must sum to records_extracted."
            )

        if records_extracted == 0:
            return ValidationQualityResult(
                records_extracted=0,
                records_valid=0,
                records_rejected=0,
                rejection_ratio=Decimal("0"),
            )
        rejection_ratio = Decimal(records_rejected) / Decimal(records_extracted)

        if rejection_ratio > self._max_rejection_ratio:
            raise ValidationError(
                "Validation rejection ratio exceeded the configured pipeline quality threshold.",
                error_code="VALIDATION_REJECTION_THRESHOLD_EXCEEDED",
                context={
                    "records_extracted": records_extracted,
                    "records_valid": records_valid,
                    "records_rejected": records_rejected,
                    "rejection_ratio": str(rejection_ratio),
                    "max_rejection_ratio": str(self._max_rejection_ratio),
                },
            )
        return ValidationQualityResult(
            records_extracted=records_extracted,
            records_valid=records_valid,
            records_rejected=records_rejected,
            rejection_ratio=rejection_ratio,
        )
