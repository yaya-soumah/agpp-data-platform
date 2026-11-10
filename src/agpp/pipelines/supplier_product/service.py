"""The Supplier Product pipeline: extract, validate, transform and load in one run (ADR-0014).

The service only composes the stages; business rules live in the stages.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.pipelines.supplier_product.config import SupplierProductConfig
from agpp.pipelines.supplier_product.extraction import extract_all
from agpp.pipelines.supplier_product.loading import (
    LoadResult,
    RunStatus,
    finish_run,
    load_all,
    record_failure,
    start_run,
)
from agpp.pipelines.supplier_product.transformation import transform_all
from agpp.pipelines.supplier_product.validation import validate_all
from agpp.shared.database import Pool
from agpp.shared.exceptions import AgppError
from agpp.shared.logging import get_pipeline_logger
from agpp.shared.runs import run_status_for


@dataclass(frozen=True)
class SupplierOutcome:
    """How one supplier ended: loaded, or the error that stopped it."""

    supplier_id: str
    load: LoadResult | None = None
    error: AgppError | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class RunSummary:
    """The result of one pipeline run."""

    run_id: str
    status: RunStatus
    outcomes: tuple[SupplierOutcome, ...]


def run_supplier_product(
    pool: Pool,
    config: SupplierProductConfig,
    *,
    run_id: str,
    now: datetime,
    sleep: Callable[[float], None] = time.sleep,
) -> RunSummary:
    """Run the whole pipeline once.

    A supplier that fails at any stage is reported and the others continue. An
    unexpected exception marks the run ``failed`` and is re-raised.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    start_run(pool, run_id)
    log.info("Run started", extra={"suppliers": len(config.suppliers)})
    try:
        extractions = extract_all(config, run_id=run_id, sleep=sleep)
        validations = validate_all(config, extractions, run_id=run_id, now=now)
        transformations = transform_all(config, validations, run_id=run_id)
        loads = load_all(pool, config, transformations, validations, run_id=run_id, sleep=sleep)
        outcomes = tuple(
            SupplierOutcome(load.supplier_id, load=load.result, error=load.error) for load in loads
        )
        for outcome in outcomes:
            if outcome.error is not None:
                record_failure(pool, run_id, outcome.supplier_id, outcome.error)
        status = _status(outcomes)
        finish_run(pool, run_id, status)
    except Exception:
        _mark_failed(pool, run_id)
        raise

    log.info(
        "Run finished",
        extra={
            "status": status.value,
            "succeeded": sum(1 for outcome in outcomes if outcome.succeeded),
            "failed": sum(1 for outcome in outcomes if not outcome.succeeded),
            "products_written": sum(o.load.products_written for o in outcomes if o.load),
            "products_unchanged": sum(o.load.products_unchanged for o in outcomes if o.load),
        },
    )
    return RunSummary(run_id, status, outcomes)


def _status(outcomes: Sequence[SupplierOutcome]) -> RunStatus:
    succeeded = sum(1 for outcome in outcomes if outcome.succeeded)
    return run_status_for(succeeded, len(outcomes))


def _mark_failed(pool: Pool, run_id: str) -> None:
    """Best effort: the original exception matters more than this bookkeeping."""
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    try:
        finish_run(pool, run_id, RunStatus.FAILED)
    except AgppError:
        log.exception("Could not mark the run as failed")
