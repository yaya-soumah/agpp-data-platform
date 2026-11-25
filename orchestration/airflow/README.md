# Airflow orchestration

`agpp_daily` (Airflow 3.4, see [ADR-0019](../../docs/adr/0019-orchestration-with-airflow.md))
runs: migrate -> supplier products -> [customer orders, inventory] -> data-quality checks at 02:00 UTC.
Each task runs one `agpp` command in the `agpp-app:local` image.

## Run it locally

```bash
# 1. In .env set AGPP_DATA_DIR to the absolute host path of ./data
#    (on Windows try D:/path/... ; fallback /run/desktop/mnt/host/d/path/...)
# 2. Generate sample inputs once
uv run agpp generate-sample-data
uv run agpp generate-sample-orders
# 3. Start Postgres, the mock stock feed and build the AGPP image
docker compose --profile app up -d --build postgres feed
# 4. Start Airflow
docker compose -f orchestration/airflow/docker-compose.yml --env-file .env up -d --build
```

UI: http://localhost:8081 (local only, no login). Unpause and trigger `agpp_daily`.
Stop: `docker compose -f orchestration/airflow/docker-compose.yml down`.

## Notes

- Idempotent loads make retries and manual re-triggers safe (ADR-0014).
- If supplier_product fails, orders and inventory are not run.
- The Docker socket is mounted into the scheduler only; this setup is for local use.
- The final task, `check_data_quality`, runs even when a pipeline failed (ADR-0020) and
  fails when a check fails. Results are in `operational.quality_check_results`.

## Tests

The DAG structure tests run in CI (job `orchestration`) in their own environment.
Airflow is not installed in the project venv. To run them locally, use Linux or WSL:

```bash
uv venv --python 3.12 .venv-airflow
uv pip install --python .venv-airflow/bin/python \
  -r orchestration/airflow/requirements-test.txt pytest \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.4.0/constraints-3.12.txt"
.venv-airflow/bin/python -m pytest -c orchestration/airflow/pytest.ini orchestration/airflow/tests
```
