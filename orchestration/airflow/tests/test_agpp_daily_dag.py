"""Structure tests for the agpp_daily DAG (no scheduler or database needed)."""

from pathlib import Path

import pytest
from airflow.models.dagbag import DagBag

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_DIR), include_examples=False)


def test_dags_import_without_errors(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}


def test_expected_tasks(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    assert set(dag.task_ids) == {
        "migrate",
        "run_supplier_product",
        "run_customer_orders",
        "run_inventory",
    }


def test_dependencies(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    assert dag.get_task("migrate").downstream_task_ids == {"run_supplier_product"}
    assert dag.get_task("run_supplier_product").downstream_task_ids == {
        "run_customer_orders",
        "run_inventory",
    }
    assert dag.get_task("run_customer_orders").downstream_task_ids == set()
    assert dag.get_task("run_inventory").downstream_task_ids == set()


def test_orders_and_inventory_are_independent(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    assert dag.get_task("run_inventory").upstream_task_ids == {"run_supplier_product"}
    assert dag.get_task("run_customer_orders").upstream_task_ids == {"run_supplier_product"}


def test_run_settings(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert all(task.retries == 1 for task in dag.tasks)

def test_tasks_pass_only_the_subcommand(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    commands = {task.task_id: task.command for task in dag.tasks}
    assert commands == {
        "migrate": ["migrate"],
        "run_supplier_product": ["run-supplier-product"],
        "run_customer_orders": ["run-customer-orders"],
        "run_inventory": ["run-inventory"],
    }


def test_tasks_join_the_agpp_network_and_mount_data(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    for task in dag.tasks:
        assert task.network_mode == "agpp_default"
        assert [m["Target"] for m in task.mounts] == ["/app/data"]


def test_task_environment_targets_compose_services(dagbag: DagBag) -> None:
    dag = dagbag.get_dag("agpp_daily")
    assert dag is not None
    for task in dag.tasks:
        assert task.environment["POSTGRES_HOST"] == "postgres"
        assert task.environment["INVENTORY_API_URL"] == "http://feed:8080"
        assert task.environment["AGPP_ENV"] == "production"
