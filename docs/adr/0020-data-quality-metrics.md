# ADR-0020: Data-quality metrics

- Status: Accepted
- Date: 2026-11-25

## Context
Each pipeline validates its input and applies a quality gate (ADR-0012), but
nothing measures the state of the warehouse after loading: freshness, the share
of rows loaded against the unknown member, coverage between facts and
dimensions, and the health of the latest runs. These are properties of the
platform, not of one pipeline.

## Decision
1. Checks are configuration. `config/pipelines/data_quality.yaml` lists checks;
   each has a name, a description, one read-only SQL query returning a single
   number, a comparison (`max` or `min`) and `warn` and `fail` thresholds. The
   file sits in `config/pipelines/` so the existing layered loader is reused;
   data quality is a platform job, not a pipeline.
2. The engine is generic and lives in `agpp.shared.quality`. It contains no
   knowledge of any table.
3. Each check runs in its own read-only transaction with a 30 second statement
   timeout. A check that cannot run is reported as `error`; the other checks
   still run.
4. Statuses: `pass`, `warn` (past `warn`), `fail` (past `fail`), `no_data`
   (the query returned no row or NULL) and `error`. `no_data` is reported but
   never fails the run: an empty warehouse is empty, not broken.
5. Every run stores its results in `operational.quality_check_results`
   (one row per check, unique per run id), so trends can be queried.
6. `agpp check-data-quality` exits 1 when any check is `fail` or `error`;
   `warn` exits 0 and is logged as a warning.
7. Checks only measure. They never modify data, and are not part of any
   pipeline run. The orchestrator runs them after the pipelines (ADR-0019).
8. Shares are preferred over counts for thresholds, because volumes vary.

## Consequences
+ A new check is a YAML change, reviewed like code.
+ Quality history lives next to run history.
- SQL in YAML is trusted configuration. The read-only transaction is a safety
  net against mistakes, not a security boundary.
- Checks are tied to the warehouse schema; a schema change must update them.
