# ADR-0007: Exceptions and error handling

- **Status:** Accepted
- **Date:** 2026-10-28
- **Related decisions:** 07 (Pipeline Flow), 09 (Logging), 10 (Exceptions),
  13 (Idempotency)

## Context

Operators need to
know which stage failed and whether trying again could help. Callers need to
distinguish bad data from a broken dependency without parsing messages.

## Decision

1. Every error raised by AGPP code derives from `AgppError`. Modules under
   `agpp.shared.exceptions` follow the lifecycle: `configuration`,
   `extraction`, `validation`, `transformation`, `loading`, plus
   `infrastructure` for dependencies (database, network).
2. Each error carries:
   - `stage` (class attribute): where it belongs, used in logs and metrics;
   - `retryable` (class attribute): whether repeating the operation may
     succeed. Only transient infrastructure and source-availability errors
     are retryable;
   - `context` (instance dict): small diagnostic facts such as a file name
     or row count. Never secrets or whole records.
3. **Wrapping.** Third-party and built-in exceptions are caught where they
   occur and re-raised as the matching AGPP error with `raise ... from
   original`. A bare `except Exception` is allowed only at the top level.
4. **Bad records are data, not exceptions.** Validators return result
   objects that list rejected rows. A stage raises only when it cannot
   continue: `SchemaValidationError` (the structure is wrong) or
   `QualityThresholdExceededError` (too many rejected records).
5. **Retry.** Only `retryable` errors are retried, with bounded attempts and
   exponential backoff. Everything else fails fast. Retried operations must
   be idempotent.
6. **Logging.** The layer that handles an error logs it, once, with
   `logger.exception`, passing `extra={"stage": error.stage,
   "error_context": error.context}`. Layers that re-raise do not log, so an
   error is never logged twice.
7. Generic utilities (for example dates) signal invalid arguments with the
   built-in `ValueError`; the calling stage wraps it in its own error.

## Consequences

### Positive
- Operators and orchestration can act on `stage` and `retryable`.
- Failures carry diagnostic context without leaking secrets.

### Negative / trade-offs
- Wrapping needs discipline at every boundary; reviews must check it.
- Context is free-form, so it needs care to stay small and non-sensitive.

### Follow-ups
- Add the retry helper and date utilities.
- Validation result objects arrive with the Supplier Product pipeline.
