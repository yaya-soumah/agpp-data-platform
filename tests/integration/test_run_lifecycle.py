from agpp.shared.database import Pool, connection
from agpp.shared.runs import RunStatus, finish_run, start_run


def test_another_pipeline_can_use_the_run_lifecycle(warehouse: Pool) -> None:
    start_run(warehouse, "run-1", "customer_orders")
    finish_run(warehouse, "run-1", RunStatus.SUCCEEDED)

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT pipeline, status, finished_at IS NOT NULL FROM operational.pipeline_runs"
        ).fetchone()
    assert row == ("customer_orders", "succeeded", True)


def test_starting_the_same_run_twice_changes_nothing(warehouse: Pool) -> None:
    start_run(warehouse, "run-1", "customer_orders")
    start_run(warehouse, "run-1", "customer_orders")

    with connection(warehouse) as conn:
        count = conn.execute("SELECT count(*) FROM operational.pipeline_runs").fetchone()
    assert count == (1,)
