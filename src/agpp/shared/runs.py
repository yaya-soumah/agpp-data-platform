"""Run lifecycle bookkeeping shared by every pipeline (ADR-0014, ADR-0017)."""

from enum import StrEnum

from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import AgppError

MAX_ERROR_MESSAGE = 500


class RunStatus(StrEnum):
    """Lifecycle and outcome of a pipeline run."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


def run_status_for(succeeded: int, total: int) -> RunStatus:
    """Succeeded if every unit succeeded, failed if none did, otherwise partial."""
    if succeeded == total:
        return RunStatus.SUCCEEDED
    if succeeded == 0:
        return RunStatus.FAILED
    return RunStatus.PARTIAL


def error_summary(error: AgppError) -> str:
    """The error message, shortened to fit a result table."""
    return str(error)[:MAX_ERROR_MESSAGE]


def start_run(pool: Pool, run_id: str, pipeline: str) -> None:
    """Record that a run has started. Starting the same run again changes nothing."""
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.pipeline_runs (run_id, pipeline, status)"
            " VALUES (%s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
            (run_id, pipeline, RunStatus.RUNNING.value),
        )


def finish_run(pool: Pool, run_id: str, status: RunStatus) -> None:
    """Record the final status and the finish time of a run."""
    with connection(pool) as conn:
        conn.execute(
            "UPDATE operational.pipeline_runs SET status = %s, finished_at = now()"
            " WHERE run_id = %s",
            (status.value, run_id),
        )
