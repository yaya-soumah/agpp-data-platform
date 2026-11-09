# ADR-0017: Shared building blocks

- **Status:** Accepted
- **Date:** 2026-11-09
- **Related decisions:** 02 (Pipeline Isolation), 03 (Shared Infrastructure),
  14 (Extensibility)

## Context

The Supplier Product pipeline is complete and a second pipeline is about to
start. Some of its code is generic and would otherwise be copied. Moving code
too early creates abstractions nobody asked for, so the rule is: **code moves to
`agpp.shared` when a second pipeline demonstrably needs it** (ADR-0001, rule 5).

## Decision

1. **Moved now** (the second pipeline needs each of them unchanged):
   - `RetryConfig` (with a `policy()` method) for retry settings in pipeline
     configuration.
   - The run lifecycle: `RunStatus`, `start_run`, `finish_run`, the rule that
     turns counts into a run status, and the shortening of error messages.
   - The CSV reader and `RawRecord`: header normalization, byte-order mark,
     ragged rows, line numbers and the error mapping of ADR-0011.
2. **Stays in each pipeline:** the stage loops and their outcome types,
   models, business rules, the quality gate wiring, transformation, loading
   and each pipeline's result table. The loops differ in what they carry and
   log; abstracting them now would be speculation.
3. **Revisit once the second pipeline exists:** a generic isolation loop and
   outcome type if the duplication turns out to be identical; `RejectedRecord`
   and its storage (the shared `rejected_records` table names its key column
   `supplier_id`, which Customer Orders will need renamed to `source_id`, done
   with its migration in Day 16).
4. **A behavior-preserving refactor is proven by tests that did not change.**
   The refactor PR adds tests for the new shared code and must not modify any
   existing test file.
5. **Boundaries are enforced by tooling.** import-linter checks in CI that
   `agpp.main` may import pipelines and shared code, pipelines may import shared
   code only, and shared code imports neither; and, once Customer Orders exists,
   that the two pipelines do not import each other (fulfils the ADR-0001
   follow-up).

## Consequences

### Positive
- The second pipeline starts with tested building blocks and no copies.
- Boundaries are checked on every change.

### Negative / trade-offs
- A small amount of shared code has two users, so changes to it need care.
- One more CI check to maintain.

### Follow-ups
- The refactor and the import-linter contracts.
- Rename the reject key column with the Customer Orders migration.
