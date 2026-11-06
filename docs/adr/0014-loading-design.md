# ADR-0014: Loading design

- **Status:** Accepted
- **Date:** 2026-11-05
- **Related decisions:** 08 (Orchestration), 09 (Logging), 12 (Warehouse
  separation), 13 (Idempotency)

## Context

Validated and transformed data must reach the warehouse so that a rerun, a
partial failure or a late file never leaves inconsistent data. Operators also
need to see what each run did.

## Decision

1. **One transaction per supplier.** For each supplier, in this order and in a
   single transaction: upsert `dim_supplier`; look up its `supplier_key`; upsert
   `dim_product`; store the rejected records; record the supplier's result.
   Either all of it commits or none of it does.
2. **Suppliers are independent.** A supplier whose load fails is rolled back
   and reported; the others are unaffected.
3. **Idempotent upserts** on the business keys (ADR-0009). A rerun with the
   same input writes nothing and leaves `updated_at` untouched.
4. **Late data never wins.** A product row is updated only if the incoming
   `source_updated_at` is not older than the stored one. Equal timestamps
   apply, so a corrected file with the same timestamp still takes effect.
5. **Absent products are left alone.** A product missing from a new file is
   neither deleted nor deactivated; catalogs may be partial. Deactivation only
   happens when a supplier sends `is_active = false`.
6. **Retry.** A load that fails with a retryable error (a lost database
   connection) is repeated with the policy from configuration. This is safe
   because the transaction is atomic and the upserts are idempotent. Other
   database errors become `WarehouseWriteError` and are not retried.
7. **Run bookkeeping.** `operational.pipeline_runs` has one row per run with a
   status (`running`, `succeeded`, `partial`, `failed`).
   `operational.supplier_run_results` has one row per supplier and run:
   `loaded` with its counts (written inside the supplier's transaction), or
   `failed` with the stage and a short message (written after the failure).
8. **Rejected records** are stored per run with line number, stage, reasons and
   raw values (ADR-0012). A supplier that fails the quality gate stores no
   rejects, only the failure; its counts are in the log and the error context.
   This is a known limitation.
9. **Run status.** `succeeded` if every supplier loaded, `failed` if none did,
   otherwise `partial`. An unexpected exception marks the run `failed` and is
   re-raised.
10. **Logging.** One line per supplier with the counts written and unchanged;
    failures are logged once, at the stage (ADR-0007).

## Consequences

### Positive
- A failed load leaves no half-written supplier.
- Reruns and retries are safe; late files cannot revert newer data.
- Every run is auditable in `operational`.

### Negative / trade-offs
- Products a supplier stops sending stay active until the supplier says
  otherwise; a later ADR may add a staleness rule.
- Rejects of gate-failed suppliers are not stored.

### Follow-ups
- Loading stage, pipeline service and the run command.
- Later: orchestration of the run (Airflow) and staleness rules.
