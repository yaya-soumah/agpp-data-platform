# ADR-0013: Transformation design

- **Status:** Accepted
- **Date:** 2026-11-04
- **Related decisions:** 06 (Business Models), 07 (Pipeline Flow),
  10 (Exceptions), 13 (Idempotency)

## Context

Validated products must become rows that match the warehouse model
(ADR-0009, ADR-0010). The transformation must be predictable: the same input
always gives the same output, so that loading it twice changes nothing.

## Decision

1. **Pure functions.** Transformation does no I/O and reads no clock. The same
   validated input gives equal output.
2. **Input and output.** Input is a supplier plus its valid `SupplierProduct`
   records. Output is a `TransformedBatch`: one `SupplierRow` and a tuple of
   `ProductRow` objects, both Pydantic models in the pipeline package.
3. **Rules.**
   - `product_id = "<supplier_id>:<supplier_sku>"` (the business key).
   - Repeated whitespace in `product_name` and `category` is collapsed to one
     space. `supplier_sku` and `currency` are never altered here.
   - `unit_price` is fixed to four decimals so equal prices are stored and
     compared identically.
   - The supplier's `updated_at` becomes `source_updated_at` (UTC).
4. **Surrogate keys are not assigned here.** Rows carry business keys only;
   the loader resolves `supplier_key` against the warehouse (ADR-0009).
5. **Defensive checks.** A product that does not belong to the supplier, or a
   repeated `product_id` after validation, raises `TransformationError`. These
   mean a bug upstream, not bad data.
6. **Isolation.** The stage transforms each supplier independently, carries
   earlier errors through, and reports a failing supplier without stopping the
   others.
7. **Suppliers with no valid products** still yield a `SupplierRow`, so
   the supplier dimension stays current.
8. **Logging.** One line per supplier with the number of products.

## Consequences

### Positive
- Transformation is trivial to test and cannot fail on I/O.
- Equal inputs give equal rows, which is what makes idempotent loading work.

### Negative / trade-offs
- Two near-identical shapes (`SupplierProduct` and `ProductRow`) exist; the
  second is the warehouse contract and may diverge.

### Follow-ups
- The warehouse tables these rows map to.
- Loading, run summaries and the pipeline service.
