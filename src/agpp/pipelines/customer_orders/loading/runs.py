"""Run bookkeeping of the Customer Orders pipeline: the shared lifecycle plus its own result."""

from agpp.pipelines.customer_orders import PIPELINE_NAME
from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import AgppError
from agpp.shared.runs import RunStatus, error_summary, finish_run
from agpp.shared.runs import start_run as _start_run

__all__ = ["RunStatus", "finish_run", "record_failure", "start_run"]


def start_run(pool: Pool, run_id: str) -> None:
    """Record that a Customer Orders run has started."""
    _start_run(pool, run_id, PIPELINE_NAME)


def record_failure(pool: Pool, run_id: str, error: AgppError) -> None:
    """Record that the run failed, with the stage and a short message."""
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO "
            "operational.order_run_results (run_id, status, failed_stage, error_message)"
            " VALUES (%s, 'failed', %s, %s)"
            " ON CONFLICT (run_id) DO UPDATE SET status = EXCLUDED.status,"
            " failed_stage = EXCLUDED.failed_stage, error_message = EXCLUDED.error_message,"
            " recorded_at = now()",
            (run_id, error.stage, error_summary(error)),
        )
