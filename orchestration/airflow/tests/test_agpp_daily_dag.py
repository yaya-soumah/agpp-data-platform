"""Structure tests for the agpp_daily DAG (no scheduler or database needed).

The DAG file is imported directly instead of through Airflow's DagBag, whose API changes
between 3.x releases. An import error in the DAG file fails every test here.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

DAG_FILE = Path(__file__).resolve().parents[1] / "dags" / "agpp_daily.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("agpp_daily_dag", DAG_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dag():  # type: ignore[no-untyped-def]
    return _load_module().dag


def test_the_dag_file_defines_the_dag(dag) -> None:  # type: ignore[no-untyped-def]
    assert dag.dag_id == "agpp_daily"


def test_expected_tasks(dag) -> None:  # type: ignore[no-untyped-def]
    assert set(dag.task_ids) == {
        "migrate",
        "run_supplier_product",
        "run_customer_orders",
        "run_inventory",
        "check_data_quality",
    }


def test_dependencies(dag) -> None:  # type: ignore[no-untyped-def]
    assert dag.get_task("migrate").downstream_task_ids == {"run_supplier_product"}
    assert dag.get_task("run_supplier_product").downstream_task_ids == {
        "run_customer_orders",
        "run_inventory",
    }
    assert dag.get_task("run_customer_orders").downstream_task_ids == {"check_data_quality"}
    assert dag.get_task("run_inventory").downstream_task_ids == {"check_data_quality"}
    assert dag.get_task("check_data_quality").downstream_task_ids == set()


def test_orders_and_inventory_are_independent(dag) -> None:  # type: ignore[no-untyped-def]
    assert dag.get_task("run_inventory").upstream_task_ids == {"run_supplier_product"}
    assert dag.get_task("run_customer_orders").upstream_task_ids == {"run_supplier_product"}


def test_run_settings(dag) -> None:  # type: ignore[no-untyped-def]
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert all(task.retries == 1 for task in dag.tasks)


def test_tasks_pass_only_the_subcommand(dag) -> None:  # type: ignore[no-untyped-def]
    commands = {task.task_id: task.command for task in dag.tasks}
    assert commands == {
        "migrate": ["migrate"],
        "run_supplier_product": ["run-supplier-product"],
        "run_customer_orders": ["run-customer-orders"],
        "run_inventory": ["run-inventory"],
        "check_data_quality": ["check-data-quality"],
    }


def test_tasks_join_the_agpp_network_and_mount_data(dag) -> None:  # type: ignore[no-untyped-def]
    for task in dag.tasks:
        assert task.network_mode == "agpp_default"
        assert [mount["Target"] for mount in task.mounts] == ["/app/data"]


def test_task_environment_targets_compose_services(dag) -> None:  # type: ignore[no-untyped-def]
    for task in dag.tasks:
        assert task.environment["POSTGRES_HOST"] == "postgres"
        assert task.environment["INVENTORY_API_URL"] == "http://feed:8080"
        assert task.environment["AGPP_ENV"] == "production"


def test_the_quality_check_waits_for_both_pipelines_and_always_runs(dag) -> None:  # type: ignore[no-untyped-def]
    task = dag.get_task("check_data_quality")
    assert task.upstream_task_ids == {"run_customer_orders", "run_inventory"}
    assert task.trigger_rule == "all_done"
    assert dag.get_task("run_inventory").trigger_rule == "all_success"
