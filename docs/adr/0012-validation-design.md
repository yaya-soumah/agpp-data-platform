# ADR-0012: Validation design

- **Status:** Accepted
- **Date:** 2026-11-03
- **Related decisions:** 06 (Business Models), 07 (Pipeline Flow),
  09 (Logging), 10 (Exceptions)

## Context

Extraction hands over raw text records (ADR-0011). Validation decides which
records are fit to load, explains every rejection, and stops a supplier whose
file is too broken to trust (ADR-0010). Rejections must be countable and
traceable to a source line.

## Decision

1. **Order of checks** for each supplier's file:
   1. **Schema** (file level): required columns must exist.
   2. **Parsing** (row level): each record is parsed by the `SupplierProduct`
      model; structurally broken rows flagged by the extractor are rejected
      here.
   3. **Business rules** (row level, from configuration): allowed currencies,
      maximum price, no timestamps beyond the future tolerance.
   4. **Duplicates** (across rows).
   5. **Quality gate** (file level): too many rejects stops the supplier.
   A row rejected at one step is not checked by later steps.
2. **Schema.** A missing required column raises `SchemaValidationError`
   before any row is read; an empty file fails here too. Columns that are
   not part of the contract are ignored and reported, never rejected.
   Optional columns may be absent, and a blank optional cell uses the default.
3. **Rejects are data.** A `RejectedRecord` keeps the supplier, the source line
   number, the step that rejected it, every reason found at that step, and the
   raw values. Reasons name the field and the rule, never echo secrets.
4. **Result.** `ValidationResult` holds the valid products, the rejects, the
   number of rows read and the ignored columns, with the reject ratio.
5. **Duplicates.** The key is the supplier plus the normalized `supplier_sku`.
   The row with the latest `updated_at` is kept; on a tie, the later line
   wins. The others are rejected with a reference to the kept line.
6. **Quality gate.** Per supplier, `rejected / rows_read` above
   `max_reject_ratio` raises `QualityThresholdExceededError`. A ratio equal to
   the limit passes. A file with a header but no data rows passes with a warning.
7. **Isolation.** Suppliers are validated independently, as in extraction. A
   supplier whose extraction failed is carried through with its error. A
   supplier that fails validation is reported and skipped; nothing of it is
   loaded.
8. **Clock.** Business rules receive `now` as a parameter, so validation is
   deterministic and testable.
9. **Logging.** One line per supplier with counts per rejection step;
   failures are logged once, at the stage (ADR-0007).

## Consequences

### Positive
- Every rejection is explainable and traceable to a line.
- The quality gate protects the warehouse from broken files.
- Each check is a small pure function that is easy to test.

### Negative / trade-offs
- Sequential checks mean a row with both a parsing and a business problem
  shows only the parsing problem until it is fixed.
- Reject records store raw values, which must stay free of sensitive data;
  this is acceptable for product catalogs.

### Follow-ups
- Parsing, business rules, duplicates, quality gate and stage.
- Transformation, then loading rejects to `operational.rejected_records`.
