"""Daily AGPP workflow (ADR-0019).

migrate -> supplier_product -> [customer_orders, inventory]

Each task runs one AGPP CLI command in the AGPP container image. This module
never imports `agpp`: the CLI is the contract between orchestration and code.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG

AGPP_IMAGE = os.environ.get("AGPP_IMAGE", "agpp-data-platform-app:latest")
DOCKER_NETWORK = os.environ.get("AGPP_DOCKER_NETWORK", "agpp-data-platform_default")
CLI_PREFIX = ["agpp"]  # confirmed against the Dockerfile ENTRYPOINT in PR 2


def _agpp_task(command: str) -> DockerOperator:
    """Build a task that runs `agpp <command>` in the AGPP image."""
    return DockerOperator(
        task_id=command.replace("-", "_"),
        image=AGPP_IMAGE,
        command=[*CLI_PREFIX, command],
        network_mode=DOCKER_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        mount_tmp_dir=False,
    )


with DAG(
    dag_id="agpp_daily",
    description="Daily AGPP platform run: supplier products, then orders and inventory.",
    schedule="0 2 * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=2),
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["agpp"],
) as dag:
    migrate = _agpp_task("migrate")
    supplier_product = _agpp_task("run-supplier-product")
    customer_orders = _agpp_task("run-customer-orders")
    inventory = _agpp_task("run-inventory")

    migrate >> supplier_product >> [customer_orders, inventory]
