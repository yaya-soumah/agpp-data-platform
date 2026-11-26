# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-11-26

First complete release: three pipelines, one warehouse, daily orchestration and
data-quality checks.

### Added

- **Foundations**: single-repository `src/agpp` layout, quality gates and CI (pytest with an
  85% branch-coverage gate, ruff, mypy, import-linter), layered YAML configuration with
  environment variables, structured logging, an exception hierarchy that carries stage and
  retryability, a retry helper and UTC date utilities
  ([ADR-0001](docs/adr/0001-single-repository-and-package-layout.md) to
  [ADR-0007](docs/adr/0007-exceptions-and-error-handling.md)).
- **Warehouse**: PostgreSQL with `operational` and `warehouse` schemas, checksummed SQL
  migrations, `dim_date`, an idempotent upsert helper and modeling conventions with unknown
  members ([ADR-0008](docs/adr/0008-warehouse-separation-and-database-access.md),
  [ADR-0009](docs/adr/0009-warehouse-modeling-conventions.md)).
- **Supplier Product pipeline**: CSV extraction with retry, validation (schema, parsing,
  business rules, duplicates, quality gate), transformation and atomic per-supplier loading
  into `dim_supplier` and `dim_product`, with run bookkeeping and stored rejects
  ([ADR-0010](docs/adr/0010-supplier-product-pipeline-contract.md) to
  [ADR-0014](docs/adr/0014-loading-design.md)).
- **Customer Orders pipeline**: order file to `dim_customer` and `fact_order_line` in one
  transaction, with late-arriving products loaded against the unknown member
  ([ADR-0016](docs/adr/0016-customer-orders-pipeline-contract.md)).
- **Inventory pipeline**: paginated HTTP stock feed with a snapshot consistency check,
  `dim_location` and the periodic `fact_inventory_snapshot`, plus a local mock feed
  ([ADR-0018](docs/adr/0018-inventory-pipeline-contract.md)).
- **Shared building blocks** moved to `agpp.shared` only when a second pipeline needed them,
  with import-linter contracts for layers and pipeline independence
  ([ADR-0017](docs/adr/0017-shared-building-blocks.md)).
- **Containers**: multi-stage, non-root image and Docker Compose services for PostgreSQL and
  the mock feed ([ADR-0015](docs/adr/0015-containerization.md)).
- **Orchestration**: Apache Airflow 3.4 `agpp_daily` DAG that runs the CLI in the project
  image, with structure tests in CI
  ([ADR-0019](docs/adr/0019-orchestration-with-airflow.md)).
- **Data quality**: configurable read-only SQL checks with warn and fail thresholds, stored
  results, a latest-results view and the `check-data-quality` command
  ([ADR-0020](docs/adr/0020-data-quality-metrics.md)).

[Unreleased]: https://github.com/yaya-soumah/agpp-data-platform/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yaya-soumah/agpp-data-platform/releases/tag/v1.0.0
