import pytest

from agpp.pipelines.supplier_product.loading.runs import (
    MAX_ERROR_MESSAGE,
    RunStatus,
    finish_run,
    record_failure,
    start_run,
)
from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import (
    InfrastructureError,
    QualityThresholdExceededError,
)


def _run_row(pool: Pool) -> tuple[object, ...]:
    with connection(pool) as conn:
        row = conn.execute(
            "SELECT pipeline, status, finished_at IS NOT NULL FROM operational.pipeline_runs"
            " WHERE run_id = 'run-1'"
        ).fetchone()
    assert row is not None
    return row


def test_a_started_run_is_recorded_as_running(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    assert _run_row(warehouse) == ("supplier_product", "running", False)


def test_starting_a_run_twice_changes_nothing(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")
    start_run(warehouse, "run-1")

    with connection(warehouse) as conn:
        count = conn.execute("SELECT count(*) FROM operational.pipeline_runs").fetchone()
    assert count == (1,)


def test_finishing_a_run_records_status_and_time(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    finish_run(warehouse, "run-1", RunStatus.PARTIAL)

    assert _run_row(warehouse) == ("supplier_product", "partial", True)


def test_a_failure_is_recorded_with_its_stage(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    record_failure(warehouse, "run-1", "SUP-002", QualityThresholdExceededError("too many"))

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT status, failed_stage, error_message FROM operational.supplier_run_results"
            " WHERE supplier_id = 'SUP-002'"
        ).fetchone()
    assert row == ("failed", "validation", "too many")


def test_long_messages_are_truncated(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    record_failure(warehouse, "run-1", "SUP-002", QualityThresholdExceededError("x" * 2000))

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT length(error_message) FROM operational.supplier_run_results"
        ).fetchone()
    assert row == (MAX_ERROR_MESSAGE,)


def test_recording_the_same_failure_twice_keeps_one_row(warehouse: Pool) -> None:
    start_run(warehouse, "run-1")

    record_failure(warehouse, "run-1", "SUP-002", QualityThresholdExceededError("first"))
    record_failure(warehouse, "run-1", "SUP-002", QualityThresholdExceededError("second"))

    with connection(warehouse) as conn:
        rows = conn.execute("SELECT error_message FROM operational.supplier_run_results").fetchall()
    assert rows == [("second",)]


def test_a_failure_for_an_unknown_run_is_a_database_error(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        record_failure(warehouse, "missing", "SUP-002", QualityThresholdExceededError("x"))

    assert info.value.context["sqlstate"] == "23503"
