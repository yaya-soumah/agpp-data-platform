"""The Customer Orders pipeline: extract, validate, transform and load one file (ADR-0016).

The service only composes the stages; business rules live in the stages.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from agpp.pipelines.customer_orders import PIPELINE_NAME
from agpp.pipelines.customer_orders.config import CustomerOrdersConfig
from agpp.pipelines.customer_orders.extraction import extract_orders
from agpp.pipelines.customer_orders.loading import (
    LoadResult,
    RunStatus,
    finish_run,
    load_orders,
    record_failure,
    start_run,
)
from agpp.pipelines.customer_orders.transformation import transform_orders
from agpp.pipelines.customer_orders.validation import validate_orders
from agpp.shared.database import Pool
from agpp.shared.exceptions import AgppError
from agpp.shared.logging import get_pipeline_logger


@dataclass(frozen=True)
class RunSummary:
    """The result of one pipeline run: loaded, or the error that stopped it."""

    run_id: str
    status: RunStatus
    load: LoadResult | None = None
    error: AgppError | None = None


def run_customer_orders(
    pool: Pool,
    config: CustomerOrdersConfig,
    *,
    run_id: str,
    now: datetime,
    sleep: Callable[[float], None] = time.sleep,
) -> RunSummary:
    """Run the whole pipeline once.

    There is one file per run, so any ``AgppError`` ends the run as ``failed``,
    recorded with its stage. An unexpected exception marks the run ``failed``
    and is re-raised.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    start_run(pool, run_id)
    log.info("Run started", extra={"source": config.source.path})
    try:
        try:
            content = extract_orders(config, run_id=run_id, sleep=sleep)
            validation = validate_orders(
                content, config.source.path, config.quality, run_id=run_id, now=now
            )
            transformed = transform_orders(validation, run_id=run_id)
            load = load_orders(
                pool,
                run_id=run_id,
                transformed=transformed,
                validation=validation,
                retry_policy=config.loading.policy(),
                sleep=sleep,
            )
        except AgppError as error:
            log.exception(
                "Run failed", extra={"stage": error.stage, "error_context": error.context}
            )
            record_failure(pool, run_id, error)
            finish_run(pool, run_id, RunStatus.FAILED)
            return RunSummary(run_id, RunStatus.FAILED, error=error)
        finish_run(pool, run_id, RunStatus.SUCCEEDED)
    except Exception:
        _mark_failed(pool, run_id)
        raise

    log.info(
        "Run finished",
        extra={
            "status": RunStatus.SUCCEEDED.value,
            "lines_written": load.lines_written,
            "lines_unchanged": load.lines_unchanged,
            "unknown_product_lines": load.unknown_product_lines,
            "rejects_stored": load.rejects_stored,
        },
    )
    return RunSummary(run_id, RunStatus.SUCCEEDED, load=load)


def _mark_failed(pool: Pool, run_id: str) -> None:
    """Best effort: the original exception matters more than this bookkeeping."""
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    try:
        finish_run(pool, run_id, RunStatus.FAILED)
    except AgppError:
        log.exception("Could not mark the run as failed")
