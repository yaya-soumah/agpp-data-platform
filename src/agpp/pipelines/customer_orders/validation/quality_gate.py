"""File-level quality gate (ADR-0010, ADR-0016)."""

from agpp.pipelines.customer_orders.config import QualityConfig
from agpp.pipelines.customer_orders.validation.result import ValidationResult
from agpp.shared.exceptions import QualityThresholdExceededError


def check_quality(result: ValidationResult, quality: QualityConfig) -> None:
    """Raise if more than ``max_reject_ratio`` of the rows were rejected.

    A ratio equal to the limit passes, and so does a file without data rows.
    """
    if result.reject_ratio <= quality.max_reject_ratio:
        return
    rejected = len(result.rejected)
    raise QualityThresholdExceededError(
        f"{rejected} of {result.rows_read} rows rejected ({result.reject_ratio:.1%}), "
        f"above the allowed {quality.max_reject_ratio:.1%}",
        context={
            "source": result.source_id,
            "rows_read": result.rows_read,
            "rejected": rejected,
            "reject_ratio": round(result.reject_ratio, 4),
            "max_reject_ratio": quality.max_reject_ratio,
        },
    )
