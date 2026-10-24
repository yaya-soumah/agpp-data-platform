# ADR-0003: Testing strategy

- **Status:** Accepted
- **Date:** 2026-10-24
- **Related decisions:** 11 (Testing strategy), 13 (Idempotency)

## Context

Every important component must be testable independently. Some tests
need only Python; others need real services (PostgreSQL, FTP). Mixing
them makes the default test run slow and dependent on Docker.

## Decision

1. Tests live in two folders: `tests/unit/` and `tests/integration/`.
   The folder decides the marker (`unit`, `integration`), applied
   automatically in `tests/conftest.py`.
2. **Unit tests** use no network and no database. They are the default
   run: `uv run pytest` executes everything except `integration`.
3. **Integration tests** use real services started with Docker Compose.
   They run explicitly with `-m integration` and in a dedicated CI job.
4. **Coverage** is measured on `src/agpp` with branch coverage and a
   minimum of 85%, enforced by `uv run pytest` itself.
5. **Tests are type-checked** (strict mypy) like production code.
6. Idempotency is verified by running a pipeline twice on
   the same input in integration tests and asserting identical results.

## Alternatives considered

| Option | Why not |
|---|---|
| Mock the database in all tests | Hides SQL and driver issues, especially for idempotent upserts. |
| One test run for everything | Requires Docker for every local run and slows feedback. |
| Coverage in a separate command | Easy to forget; the gate must be the one command. |

## Consequences

### Positive
- Fast default feedback; real-service checks where they matter.
- One command enforces tests and coverage.

### Negative / trade-offs
- An 85% threshold can push shallow tests; reviews must look at test
  quality, not only the number.
- Integration tests need a separate CI job.
