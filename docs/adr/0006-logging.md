# ADR-0006: Logging

- **Status:** Accepted
- **Date:** 2026-10-27
- **Related decisions:** 04 (Configuration first), 09 (Logging), 10 (Exceptions)

## Context

Decision 09 says everything must be logged. Logs must be readable on a
developer's terminal, machine-parseable in production, and must never leak
secrets. Logging setup must also follow the configuration rules of ADR-0005.

## Decision

1. We use the standard library `logging` module only.
2. Logging is configured **once, at startup**, from the `logging` section of
   the platform configuration (`level`, `format`, `file`, rotation settings).
   There is no separate `logging.yaml`, so logging goes through the same
   layering, placeholders and validation as everything else.
3. Handlers: a console handler on stderr, plus an optional rotating file
   handler when `logging.file` is set.
4. Formats: `console` (human-readable) and `json` (one JSON object per line).
   Timestamps are always UTC. Production uses `json`.
5. Application code never configures logging and never uses `print`. It uses
   `logging.getLogger(__name__)`, or `get_pipeline_logger(pipeline, run_id)`
   inside pipelines so every record carries `pipeline` and `run_id`.
6. Structured context is passed through `extra={...}` and appears as fields
   in JSON and as `key=value` pairs on the console.
7. What is logged: the start and end of each lifecycle stage with row counts
   and duration; warnings with counts for rejected or skipped data; errors
   with the exception.
8. **Never log** secrets, credentials, or whole records that may contain
   personal data. Configuration values are not logged, only the environment
   name.
9. `configure_logging` is idempotent and removes only the handlers it
   installed, so it can be called again (and tests can run) safely.

## Consequences

### Positive
- Consistent, searchable logs; run context on every pipeline record.
- No new runtime dependency.

### Negative / trade-offs
- A small custom JSON formatter to maintain.
- Rotating file handlers are per process and not safe for several
  processes writing the same file; production logs go to stdout/stderr.

### Follow-ups
- wire `configure_logging` into the CLI.
- Orchestration later adds the Airflow task context to `run_id`.
