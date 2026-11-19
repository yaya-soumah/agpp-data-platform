"""The Inventory pipeline: extract, validate, transform and load one feed (ADR-0018).

The service only composes the stages; business rules live in the stages.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from agpp.pipelines.inventory import PIPELINE_NAME
from agpp.pipelines.inventory.config import InventoryConfig
from agpp.pipelines.inventory.extraction import extract_inventory
from agpp.pipelines.inventory.loading import (
    LoadResult,
    RunStatus,
    finish_run,
    load_inventory,
    record_failure,
    start_run,
)
from agpp.pipelines.inventory.transformation import transform_inventory
from agpp.pipelines.inventory.validation import validate_inventory
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


def run_inventory(
    pool: Pool,
    config: InventoryConfig,
    *,
    run_id: str,
    now: datetime,
    sleep: Callable[[float], None] = time.sleep,
    client: httpx.Client | None = None,
) -> RunSummary:
    """Run the whole pipeline once.

    There is one feed per run, so any ``AgppError`` ends the run as ``failed``,
    recorded with its stage. An unexpected exception marks the run ``failed`` and is
    re-raised. A ``client`` can be passed in to avoid real network access in tests.
    """
    log = get_pipeline_logger(PIPELINE_NAME, run_id)
    start_run(pool, run_id)
    log.info("Run started", extra={"source": f"{config.source.base_url}{config.source.path}"})
    try:
        try:
            extraction = extract_inventory(config, run_id=run_id, sleep=sleep, client=client)
            validation = validate_inventory(extraction, config.quality, run_id=run_id, now=now)
            transformed = transform_inventory(validation, run_id=run_id)
            load = load_inventory(
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
            "rows_written": load.rows_written,
            "rows_unchanged": load.rows_unchanged,
            "unknown_product_rows": load.unknown_product_rows,
            "below_reorder_rows": load.below_reorder_rows,
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
