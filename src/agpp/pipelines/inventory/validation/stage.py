"""Validation stage: decide which stock items are fit to load (ADR-0012, ADR-0018)."""

from datetime import datetime

from agpp.pipelines.inventory import PIPELINE_NAME
from agpp.pipelines.inventory.config import QualityConfig
from agpp.pipelines.inventory.extraction import InventoryExtraction
from agpp.pipelines.inventory.validation.business_validator import validate_business_rules
from agpp.pipelines.inventory.validation.duplicate_detector import remove_duplicates
from agpp.pipelines.inventory.validation.quality_gate import check_quality
from agpp.pipelines.inventory.validation.result import RejectionStage, ValidationResult
from agpp.pipelines.inventory.validation.row_parser import parse_records
from agpp.pipelines.inventory.validation.schema_validator import validate_schema
from agpp.pipelines.inventory.validation.snapshot import check_snapshot
from agpp.shared.logging import get_pipeline_logger


def validate_inventory(
    extraction: InventoryExtraction,
    quality: QualityConfig,
    *,
    run_id: str,
    now: datetime,
) -> ValidationResult:
    """Run every check on the extracted feed.

    Raises ``InvalidSnapshotError`` for a stale, future or unreadable snapshot,
    ``SchemaValidationError`` for missing fields and
    ``QualityThresholdExceededError`` when too many items were rejected. An empty
    feed is valid (nothing to report) and only produces a warning.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    source_id = extraction.source_id
    snapshot_at = check_snapshot(extraction.snapshot_at, quality, now=now)

    ignored_columns: tuple[str, ...] = ()
    if extraction.records:
        ignored_columns = validate_schema(extraction.columns, source_id)
    parsed, parse_rejects = parse_records(source_id, extraction.records)
    parsed, business_rejects = validate_business_rules(
        parsed, quality, source_id=source_id, snapshot_at=snapshot_at
    )
    unique, duplicate_rejects = remove_duplicates(parsed, source_id=source_id)

    rejected = sorted(
        [*parse_rejects, *business_rejects, *duplicate_rejects],
        key=lambda record: record.line_number,
    )
    result = ValidationResult(
        source_id=source_id,
        snapshot_at=snapshot_at,
        rows_read=len(extraction.records),
        valid=tuple(record.item for record in unique),
        rejected=tuple(rejected),
        ignored_columns=ignored_columns,
    )
    check_quality(result, quality)

    log.info(
        "Inventory validated",
        extra={
            "source": source_id,
            "snapshot_at": snapshot_at.isoformat(),
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
        log.warning("Stock feed has no items", extra={"source": source_id})
    return result
