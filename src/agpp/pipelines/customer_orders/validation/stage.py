"""Validation stage: decide which order lines are fit to load (ADR-0012, ADR-0016)."""

from datetime import datetime

from agpp.pipelines.customer_orders import PIPELINE_NAME
from agpp.pipelines.customer_orders.config import QualityConfig
from agpp.pipelines.customer_orders.validation.business_validator import (
    validate_business_rules,
)
from agpp.pipelines.customer_orders.validation.duplicate_detector import remove_duplicates
from agpp.pipelines.customer_orders.validation.quality_gate import check_quality
from agpp.pipelines.customer_orders.validation.result import RejectionStage, ValidationResult
from agpp.pipelines.customer_orders.validation.row_parser import parse_records
from agpp.pipelines.customer_orders.validation.schema_validator import validate_schema
from agpp.shared.extraction import CsvContent
from agpp.shared.logging import get_pipeline_logger


def validate_orders(
    content: CsvContent,
    source_id: str,
    quality: QualityConfig,
    *,
    run_id: str,
    now: datetime,
) -> ValidationResult:
    """Run every check on the extracted file.

    Raises ``SchemaValidationError`` for a broken header and
    ``QualityThresholdExceededError`` when too many rows were rejected; the
    caller decides what a failure means for the run.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    ignored_columns = validate_schema(content.columns, source_id)
    parsed, parse_rejects = parse_records(source_id, content.records)
    parsed, business_rejects = validate_business_rules(
        parsed, quality, source_id=source_id, now=now
    )
    unique, duplicate_rejects = remove_duplicates(parsed, source_id=source_id)

    rejected = sorted(
        [*parse_rejects, *business_rejects, *duplicate_rejects],
        key=lambda record: record.line_number,
    )
    result = ValidationResult(
        source_id=source_id,
        rows_read=len(content.records),
        valid=tuple(record.line for record in unique),
        rejected=tuple(rejected),
        ignored_columns=ignored_columns,
    )
    check_quality(result, quality)

    log.info(
        "Orders validated",
        extra={
            "source": source_id,
            "rows": result.rows_read,
            "valid": len(result.valid),
            "rejected": len(result.rejected),
            "rejected_parsing": result.rejected_by(RejectionStage.PARSING),
            "rejected_business": result.rejected_by(RejectionStage.BUSINESS),
            "rejected_duplicate": result.rejected_by(RejectionStage.DUPLICATE),
            "ignored_columns": list(result.ignored_columns),
        },
    )
    if result.rows_read == 0:
        log.warning("Order file has no data rows", extra={"source": source_id})
    return result
