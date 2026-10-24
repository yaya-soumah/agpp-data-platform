# ADR-0002: Quality gates and continuous integration

- **Status:** Accepted
- **Date:** 2026-10-23
- **Related decisions:** 11 (Testing strategy), 15 (Documentation)

## Context

The platform is meant to behave like a production codebase. Quality must
not depend on individual discipline, and every change needs the same
checks regardless of who made it or when.

## Decision

1. Every change must pass four gates, run through `uv`:
   - `uv run pytest`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run mypy` (strict mode)
2. **CI is the enforcement point.** GitHub Actions runs all four gates
   on every pull request and on pushes to `main`; `main` is protected and
   requires the check to pass.
3. **pre-commit** runs fast checks locally (ruff, ruff-format, file
   hygiene). It gives early feedback and never replaces CI. mypy and
   pytest run in CI only because they are too slow for commit hooks.
4. Dependencies are locked in `uv.lock`; CI uses `uv sync --locked`, so
   a stale lockfile fails the build.
5. No Makefile or task runner: the four `uv run` commands are the
   documented interface.

## Alternatives considered

| Option | Why not |
|---|---|
| Makefile / task runner | Adds a layer to maintain with no benefit at this scale. |
| Local-only checks | Not enforceable; passes only if everyone remembers. |
| Gates in pre-commit only | Can be skipped with `--no-verify`. |

## Consequences

### Positive
- Consistent quality bar and a green `main` at all times.
- New contributors and reviewers see the standard immediately.

### Negative / trade-offs
- Strict mypy adds friction early, especially around untyped
  third-party libraries (handled case by case with documented overrides).

### Follow-ups
- Add a coverage threshold and test markers (Day 2).
- Add integration-test jobs when Postgres is introduced.
