# ADR-0019: Orchestration with Airflow

- Status: Accepted
- Date: 2026-11-23

## Context
Three pipelines run via CLI commands (ADR-0004, 0010, 0016, 0018). Nothing yet
schedules them, orders them or retries a failed run. Orders and inventory
resolve product keys loaded by supplier_product; unknown products load against
-1 and heal on rerun (ADR-0014), so the order is a quality preference, not a
correctness requirement. Orchestration must stay separate from pipeline logic.

## Decision
1. Orchestrate with Apache Airflow, pinned to 3.4.0 with the official
   constraints file.
2. Airflow lives in `orchestration/airflow/` with its own image, requirements
   and tests. It is NOT a dependency of `pyproject.toml`: its dependency tree is
   large and would constrain the pipeline packages.
3. Airflow never imports `agpp`. Each task runs the AGPP container image
   (DockerOperator) with one CLI command. The CLI is the contract.
4. One DAG, `agpp_daily`: migrate >> run-supplier-product >>
   [run-customer-orders, run-inventory]. Orders and inventory run in parallel.
5. Default trigger rule (all_success): if supplier_product fails, downstream
   tasks do not run. Failures stay visible instead of loading against -1.
6. Schedule `0 2 * * *` UTC, catchup=False, max_active_runs=1, one retry after
   5 minutes. The CLI has no date argument, so runs process "current" source
   data; logical-date partitioning is out of scope.
7. A DAG structure test (DagBag import, task ids, dependencies, schedule,
   retries) runs in its own CI job.

## Consequences
+ Pipeline code stays testable and runnable without Airflow.
+ Idempotent loads (ADR-0014) make retries and manual re-triggers safe.
- Two environments to maintain (project venv, Airflow image).
- DockerOperator needs the Docker socket mounted in the Airflow containers.

## Alternatives considered
- `run-all` command + cron container: simpler, but no UI, retries or
  dependency graph.
- Airflow as a project dependency: rejected, dependency conflicts.
- PythonOperator importing `agpp`: rejected, couples orchestration to code.
