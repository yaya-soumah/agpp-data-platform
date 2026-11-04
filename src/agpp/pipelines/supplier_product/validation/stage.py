"""Validation stage: decide which records of each supplier are fit to load (ADR-0012)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.pipelines.supplier_product.config import QualityConfig, SupplierProductConfig
from agpp.pipelines.supplier_product.extraction import ExtractionResult, SupplierExtraction
from agpp.pipelines.supplier_product.validation.business_validator import (
    validate_business_rules,
)
from agpp.pipelines.supplier_product.validation.duplicate_detector import remove_duplicates
from agpp.pipelines.supplier_product.validation.quality_gate import check_quality
from agpp.pipelines.supplier_product.validation.result import RejectionStage, ValidationResult
from agpp.pipelines.supplier_product.validation.row_parser import parse_records
from agpp.pipelines.supplier_product.validation.schema_validator import validate_schema
from agpp.shared.exceptions import AgppError
from agpp.shared.logging import get_pipeline_logger


@dataclass(frozen=True)
class SupplierValidation:
    """The outcome for one supplier: a result, or the error that stopped it."""

    supplier_id: str
    result: ValidationResult | None = None
    error: AgppError | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def validate_supplier(
    extraction: ExtractionResult, quality: QualityConfig, *, now: datetime
) -> ValidationResult:
    """Run every check for one supplier's file.

    Raises ``SchemaValidationError`` for a broken header and
    ``QualityThresholdExceededError`` when too many rows were rejected.
    """
    ignored_columns = validate_schema(extraction)
    parsed, parse_rejects = parse_records(extraction.supplier_id, extraction.records)
    parsed, business_rejects = validate_business_rules(parsed, quality, now=now)
    unique, duplicate_rejects = remove_duplicates(parsed)

    rejected = sorted(
        [*parse_rejects, *business_rejects, *duplicate_rejects],
        key=lambda record: record.line_number,
    )
    result = ValidationResult(
        supplier_id=extraction.supplier_id,
        rows_read=extraction.row_count,
        valid=tuple(record.product for record in unique),
        rejected=tuple(rejected),
        ignored_columns=ignored_columns,
    )
    check_quality(result, quality)
    return result


def validate_all(
    config: SupplierProductConfig,
    extractions: Sequence[SupplierExtraction],
    *,
    run_id: str,
    now: datetime,
) -> list[SupplierValidation]:
    """Validate every extracted supplier independently.

    A supplier whose extraction failed is carried through with that error. A
    supplier that fails validation is reported and the others continue.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    log.info("Validation started", extra={"suppliers": len(extractions)})

    outcomes: list[SupplierValidation] = []
    for extraction in extractions:
        if extraction.result is None:
            outcomes.append(SupplierValidation(extraction.supplier_id, error=extraction.error))
            continue
        try:
            result = validate_supplier(extraction.result, config.quality, now=now)
        except AgppError as error:
            log.exception(
                "Supplier validation failed",
                extra={
                    "supplier_id": extraction.supplier_id,
                    "stage": error.stage,
                    "error_context": error.context,
                },
            )
            outcomes.append(SupplierValidation(extraction.supplier_id, error=error))
            continue

        log.info(
            "Supplier validated",
            extra={
                "supplier_id": result.supplier_id,
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
            log.warning("Supplier file has no data rows", extra={"supplier_id": result.supplier_id})
        outcomes.append(SupplierValidation(extraction.supplier_id, result=result))

    failed = sum(1 for outcome in outcomes if not outcome.succeeded)
    log.info("Validation finished", extra={"succeeded": len(outcomes) - failed, "failed": failed})
    return outcomes
