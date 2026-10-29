# ADR-0008: Warehouse separation and database access

- **Status:** Accepted
- **Date:** 2026-10-29
- **Related decisions:** 12 (Warehouse separation), 13 (Idempotency),
  03 (Shared Infrastructure)

## Context

Decision 12 says operational and analytical storage have different
purposes. The platform needs one clear rule for what lives where, and one
way to talk to PostgreSQL that is explicit, testable and safe to retry.

## Decision

1. One PostgreSQL database with two schemas:
   - `operational`: pipeline run history, rejected records, migration
     bookkeeping and optional staging data. Written often, short retention,
     owned by the pipelines.
   - `warehouse`: the dimensional model (`dim_*` and `fact_*` tables). It is
     the only schema analytics consumers read, so changes to it are
     deliberate and backwards-compatible where possible.
2. Pipelines write run metadata and rejects to `operational` and load
   validated, transformed data into `warehouse`. Nothing flows from
   `warehouse` back into `operational`.
3. All SQL uses **schema-qualified table names**. We never rely on
   `search_path`.
4. Access goes through `agpp.shared.database`: a `psycopg_pool` connection
   pool created from configuration, and a `connection()` context manager
   that borrows a connection and translates driver errors into AGPP errors
   (ADR-0007). Connection errors are retryable; other database errors are
   not.
5. We use psycopg 3 with explicit SQL and no ORM. Idempotent upserts
   (`INSERT ... ON CONFLICT`) are easier to write and review as plain SQL.
6. Schema changes happen only through versioned SQL migrations (next PR).

## Consequences

### Positive
- Clear ownership and a stable consumer-facing schema.
- Moving the warehouse to its own database later is a configuration and
  pool change, not a rewrite, because names are qualified.

### Negative / trade-offs
- Both schemas share one instance, so heavy analytics could affect
  pipeline writes until they are split.
- Writing SQL by hand needs discipline and tests.

### Follow-ups
- Migrations, creating both schemas.
