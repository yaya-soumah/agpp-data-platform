"""Daily AGPP workflow (ADR-0019).

migrate -> supplier_product -> [customer_orders, inventory]

Each task runs one AGPP CLI command in the AGPP container image. The image's
ENTRYPOINT is `agpp`, so a task passes only the subcommand. This module never
imports `agpp`: the CLI is the contract between orchestration and code.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG
from docker.types import Mount

AGPP_IMAGE = os.environ.get("AGPP_IMAGE", "agpp-app:local")
DOCKER_NETWORK = os.environ.get("AGPP_DOCKER_NETWORK", "agpp_default")
DATA_DIR = os.environ.get("AGPP_DATA_DIR", "/tmp/agpp-data")
FEED_URL = os.environ.get("AGPP_FEED_URL", "http://feed:8080")

_PASSTHROUGH = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "INVENTORY_API_TOKEN",
)


def _task_environment() -> dict[str, str]:
    """Environment for task containers: fixed network facts + passthrough."""
    env = {
        "AGPP_ENV": "production",
        "POSTGRES_HOST": "postgres",
        "POSTGRES_PORT": "5432",
        "INVENTORY_API_URL": FEED_URL,
    }
    env.update({key: os.environ[key] for key in _PASSTHROUGH if key in os.environ})
    return env


def _agpp_task(command: str) -> DockerOperator:
    """Build a task that runs `agpp <command>` in the AGPP image."""
    return DockerOperator(
        task_id=command.replace("-", "_"),
        image=AGPP_IMAGE,
        command=[command],
        environment=_task_environment(),
        mounts=[Mount(source=DATA_DIR, target="/app/data", type="bind")],
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
