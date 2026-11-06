import pytest

from agpp.shared.database import Pool, connection
from agpp.shared.exceptions import InfrastructureError

FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"


def _start(pool: Pool, status: str = "running") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.pipeline_runs (run_id, pipeline, status)"
            " VALUES ('run-1', 'supplier_product', %s)",
            (status,),
        )


def _result(pool: Pool, status: str, failed_stage: str | None, run_id: str = "run-1") -> None:
    with connection(pool) as conn:
        conn.execute(
            "INSERT INTO operational.supplier_run_results"
            " (run_id, supplier_id, status, failed_stage) VALUES (%s, 'SUP-001', %s, %s)",
            (run_id, status, failed_stage),
        )


def test_a_run_status_must_be_known(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        _start(warehouse, status="weird")

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_a_supplier_result_needs_an_existing_run(warehouse: Pool) -> None:
    with pytest.raises(InfrastructureError) as info:
        _result(warehouse, "loaded", None)

    assert info.value.context["sqlstate"] == FOREIGN_KEY_VIOLATION


def test_loaded_results_have_no_failed_stage(warehouse: Pool) -> None:
    _start(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _result(warehouse, "loaded", "loading")

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_failed_results_need_a_failed_stage(warehouse: Pool) -> None:
    _start(warehouse)

    with pytest.raises(InfrastructureError) as info:
        _result(warehouse, "failed", None)

    assert info.value.context["sqlstate"] == CHECK_VIOLATION


def test_valid_results_are_accepted(warehouse: Pool) -> None:
    _start(warehouse)

    _result(warehouse, "failed", "extraction")
