"""Transformation stage: map validated order lines to warehouse rows (ADR-0013)."""

from agpp.pipelines.customer_orders import PIPELINE_NAME
from agpp.pipelines.customer_orders.transformation.rows import TransformedOrders
from agpp.pipelines.customer_orders.transformation.transformer import to_rows
from agpp.pipelines.customer_orders.validation import ValidationResult
from agpp.shared.logging import get_pipeline_logger


def transform_orders(result: ValidationResult, *, run_id: str) -> TransformedOrders:
    """Transform the valid lines. Raises ``TransformationError`` on an upstream bug."""
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    transformed = to_rows(result.valid)
    log.info(
        "Orders transformed",
        extra={"lines": len(transformed.lines), "customers": len(transformed.customers)},
    )
    return transformed
