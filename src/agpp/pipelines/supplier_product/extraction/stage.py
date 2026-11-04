"""Extraction stage: read every configured supplier source (ADR-0011)."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.pipelines.supplier_product.config import SupplierConfig, SupplierProductConfig
from agpp.pipelines.supplier_product.extraction.base import ExtractionResult, Extractor
from agpp.pipelines.supplier_product.extraction.factory import create_extractor
from agpp.shared.exceptions import AgppError
from agpp.shared.logging import get_pipeline_logger
from agpp.shared.resilience.retry import RetryPolicy, call_with_retry


@dataclass(frozen=True)
class SupplierExtraction:
    """The outcome for one supplier: a result, or the error that stopped it."""

    supplier_id: str
    result: ExtractionResult | None = None
    error: AgppError | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def extract_all(
    config: SupplierProductConfig,
    *,
    run_id: str,
    extractor_factory: Callable[[SupplierConfig], Extractor] = create_extractor,
    sleep: Callable[[float], None] = time.sleep,
) -> list[SupplierExtraction]:
    """Extract every supplier independently, retrying retryable errors.

    A supplier that still fails is reported in its outcome and the others
    continue. Errors that are not ``AgppError`` (bugs) propagate.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    policy = RetryPolicy(
        max_attempts=config.extraction.max_attempts,
        initial_delay=config.extraction.initial_delay_seconds,
    )
    log.info("Extraction started", extra={"suppliers": len(config.suppliers)})

    outcomes: list[SupplierExtraction] = []
    for supplier in config.suppliers:
        try:
            extractor = extractor_factory(supplier)
            result = call_with_retry(extractor.extract, policy, sleep=sleep)
        except AgppError as error:
            log.exception(
                "Supplier extraction failed",
                extra={
                    "supplier_id": supplier.supplier_id,
                    "stage": error.stage,
                    "error_context": error.context,
                },
            )
            outcomes.append(SupplierExtraction(supplier.supplier_id, error=error))
            continue
        log.info(
            "Supplier extracted",
            extra={
                "supplier_id": supplier.supplier_id,
                "source": result.source,
                "rows": result.row_count,
                "columns": len(result.columns),
            },
        )
        outcomes.append(SupplierExtraction(supplier.supplier_id, result=result))

    failed = sum(1 for outcome in outcomes if not outcome.succeeded)
    log.info(
        "Extraction finished",
        extra={"succeeded": len(outcomes) - failed, "failed": failed},
    )
    return outcomes
