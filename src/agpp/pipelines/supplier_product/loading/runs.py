"""Run bookkeeping in the operational schema (ADR-0014)."""

from enum import StrEnum

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import AgppError

MAX_ERROR_MESSAGE = 500


class RunStatus(StrEnum):
    """Lifecycle and outcome of a pipeline run."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


def start_run(pool: Pool, run_id: str) -> None:
    """Record that a run has started. Starting the same run again changes nothing."""
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.pipeline_runs (run_id, pipeline, status)"
            " VALUES (%s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
            (run_id, PIPELINE_NAME, RunStatus.RUNNING.value),
        )


def finish_run(pool: Pool, run_id: str, status: RunStatus) -> None:
    """Record the final status and the finish time of a run."""
    with connection(pool) as conn:
        conn.execute(
            "UPDATE operational.pipeline_runs SET status = %s, finished_at = now()"
            " WHERE run_id = %s",
            (status.value, run_id),
        )


def record_failure(pool: Pool, run_id: str, supplier_id: str, error: AgppError) -> None:
    """Record that a supplier failed, with the stage and a short message."""
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.supplier_run_results"
            " (run_id, supplier_id, status, failed_stage, error_message)"
            " VALUES (%s, %s, 'failed', %s, %s)"
            " ON CONFLICT (run_id, supplier_id) DO UPDATE SET status = EXCLUDED.status,"
            " failed_stage = EXCLUDED.failed_stage, error_message = EXCLUDED.error_message,"
            " recorded_at = now()",
            (run_id, supplier_id, error.stage, str(error)[:MAX_ERROR_MESSAGE]),
        )
