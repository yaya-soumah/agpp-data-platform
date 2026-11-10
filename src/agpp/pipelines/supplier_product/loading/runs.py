"""Run bookkeeping of the Supplier Product pipeline: the shared lifecycle plus its own results."""

from agpp.pipelines.supplier_product import PIPELINE_NAME
from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import AgppError
from agpp.shared.runs import MAX_ERROR_MESSAGE, RunStatus, error_summary, finish_run
from agpp.shared.runs import start_run as _start_run

__all__ = [
    "MAX_ERROR_MESSAGE",
    "RunStatus",
    "finish_run",
    "record_failure",
    "start_run",
]


def start_run(pool: Pool, run_id: str) -> None:
    """Record that a Supplier Product run has started."""
    _start_run(pool, run_id, PIPELINE_NAME)


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
            (run_id, supplier_id, error.stage, error_summary(error)),
        )
