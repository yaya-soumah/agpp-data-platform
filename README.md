# AGPP Data Platform

A production-style data platform for the fictitious company AGPP, built as
an engineering portfolio. Three pipelines (Supplier Product, Customer
Orders, Inventory) share one platform, one warehouse and one set of
engineering standards.

```
Supplier Product ──┐
Customer Orders ───┼──> Data Warehouse
Inventory ─────────┘
```

> **Status:** under active development. See the pull request history for
> progress.

## Principles

Each pipeline follows the same lifecycle: **extract → validate →
transform → load**. Business logic never orchestrates itself, nothing
environment-specific lives in code, and re-running a pipeline with the
same input never creates inconsistent data. The reasoning behind each
choice is recorded in [`docs/adr/`](docs/adr/).

## Requirements

- Python 3.13.1 or newer
- [uv](https://docs.astral.sh/uv/)

## Getting started

```bash
git clone https://github.com/yaya-soumah/agpp-data-platform.git
cd agpp-data-platform
uv sync
cp .env_example .env      # then edit .env with real values
uv run python -m agpp.main
```

## Quality gates

Every change must pass all four checks (enforced in CI):

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Testing

`uv run pytest` runs unit tests and enforces a minimum of 85% branch
coverage. Integration tests need Docker services and are excluded by
default:

```bash
docker compose up -d
uv run --env-file .env pytest -m integration --no-cov
```

See [ADR-0003](docs/adr/0003-testing-strategy.md).

Optional local hooks for fast feedback before each commit:

```bash
uv run pre-commit install
```

## Repository layout

| Path | Purpose |
|---|---|
| `src/agpp/pipelines/` | One folder per pipeline, each owning its business logic |
| `src/agpp/shared/` | Generic infrastructure: configuration, logging, exceptions, database |
| `config/` | Environment-specific YAML configuration (no secrets) |
| `sql/` | Warehouse DDL and migrations |
| `tests/` | Unit and integration tests |
| `docs/` | Architecture decision records and documentation |
| `data/` | Local sample and generated data (not committed) |

## Documentation

- [Architecture decision records](docs/adr/)
