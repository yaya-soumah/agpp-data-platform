"""Transformation stage: map validated stock items to warehouse rows (ADR-0013)."""

from agpp.pipelines.inventory import PIPELINE_NAME
from agpp.pipelines.inventory.transformation.rows import TransformedInventory
from agpp.pipelines.inventory.transformation.transformer import to_rows
from agpp.pipelines.inventory.validation import ValidationResult
from agpp.shared.logging import get_pipeline_logger


def transform_inventory(result: ValidationResult, *, run_id: str) -> TransformedInventory:
    """Transform the valid items. Raises ``TransformationError`` on an upstream bug."""
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    transformed = to_rows(result.snapshot_at, result.valid)
    log.info(
        "Inventory transformed",
        extra={
            "rows": len(transformed.rows),
            "locations": len(transformed.locations),
            "below_reorder_point": sum(1 for row in transformed.rows if row.below_reorder_point),
        },
    )
    return transformed
