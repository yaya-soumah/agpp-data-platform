"""Feed-level quality gate (ADR-0010, ADR-0018)."""

from agpp.pipelines.inventory.config import QualityConfig
from agpp.pipelines.inventory.validation.result import ValidationResult
from agpp.shared.exceptions import QualityThresholdExceededError


def check_quality(result: ValidationResult, quality: QualityConfig) -> None:
    """Raise if more than ``max_reject_ratio`` of the items were rejected.

    A ratio equal to the limit passes, and so does an empty feed.
    """
    if result.reject_ratio <= quality.max_reject_ratio:
        return
    rejected = len(result.rejected)
    raise QualityThresholdExceededError(
        f"{rejected} of {result.rows_read} items rejected ({result.reject_ratio:.1%}), "
        f"above the allowed {quality.max_reject_ratio:.1%}",
        context={
            "source": result.source_id,
            "rows_read": result.rows_read,
            "rejected": rejected,
            "reject_ratio": round(result.reject_ratio, 4),
            "max_reject_ratio": quality.max_reject_ratio,
        },
    )
