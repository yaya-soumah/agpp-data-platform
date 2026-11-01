# ADR-0010: Supplier Product pipeline contract

- **Status:** Accepted
- **Date:** 2026-10-31
- **Related decisions:** 04 (Configuration first), 06 (Business Models),
  07 (Pipeline Flow), 13 (Idempotency), 14 (Extensibility)

## Context

AGPP buys from several suppliers, each sending a product catalog in its own
file. The Supplier Product pipeline turns those files into trustworthy
supplier and product dimensions in the warehouse. This ADR fixes what goes
in, which rules apply, and what comes out, so extraction, validation,
transformation and loading can be built and tested independently.

## Decision

1. **Scope.** The pipeline owns suppliers and their products. Stock levels
   and orders belong to the Inventory and Customer Orders pipelines.
2. **Input.** One file per supplier, configured in
   `config/pipelines/supplier_product.yaml`. Each file has these columns
   (`supplier_id` is not in the file; extraction attaches it from the
   configuration):

   | Column | Type | Rule |
   |---|---|---|
   | `supplier_sku` | text | required, 1-50 characters |
   | `product_name` | text | required, 1-200 characters |
   | `category` | text | required, 1-100 characters |
   | `unit_price` | decimal | required, > 0, at most 4 decimal places |
   | `currency` | text | required, three letters |
   | `min_order_quantity` | integer | optional, >= 1, default 1 |
   | `lead_time_days` | integer | required, 0-365 |
   | `is_active` | boolean | optional, default true |
   | `updated_at` | timestamp | required, ISO 8601 **with** offset or `Z` |

3. **Parsing (the `SupplierProduct` model).** Types, ranges and formats are
   enforced by a Pydantic model. Harmless normalization is part of parsing:
   surrounding whitespace is trimmed, `supplier_sku` and `currency` are
   upper-cased, and timestamps are converted to UTC. Timestamps without an
   offset are rejected, never guessed.
4. **Business rules (configuration-driven).** Checked after parsing, with
   limits from the YAML: the currency must be in `allowed_currencies`,
   `unit_price` must not exceed `max_unit_price`, and `updated_at` must not
   be more than `future_tolerance_minutes` in the future.
5. **Duplicates.** Within one file, rows sharing the same normalized
   `supplier_sku` are duplicates. The row with the latest `updated_at`
   is kept; the others are rejected.
6. **Rejects are data** (ADR-0007). A bad row is recorded with its reason in
   `operational.rejected_records` and the run continues. A missing required
   column is different: it raises `SchemaValidationError` and stops the file.
7. **Quality gate.** If rejected rows exceed `max_reject_ratio` of a file's
   rows, the run raises `QualityThresholdExceededError` **before** anything is
   loaded for that file.
8. **Transformation.** The business key is
   `product_id = "<supplier_id>:<supplier_sku>"`. Names have repeated
   whitespace collapsed; prices are fixed to four decimals.
9. **Output (ADR-0009 conventions).**
   - `warehouse.dim_supplier` (business key `supplier_id`): name and country.
   - `warehouse.dim_product` (business key `product_id`): supplier,
     SKU, name, category, current unit price, currency, minimum order
     quantity, lead time, active flag and the supplier's `updated_at`.
     Type 1: a price change overwrites the row.
   - Both have an "unknown" member with key `-1`.
   - A run summary (rows read, rejected, written, unchanged) is logged and
     stored in `operational`.
10. **Extensibility.** The source type is configuration (`source.type`).
    Only `csv` exists now; `api` and `ftp` are added later as new extractors
    plus a new configuration variant, without touching validation,
    transformation or loading.
11. **Failure semantics.** An unreachable source raises
    `SourceUnavailableError` (retryable). Everything else fails fast.

## Consequences

### Positive
- Each stage has a clear contract and can be tested alone.
- Bad data is visible and countable instead of silently dropped.
- A new supplier is one configuration entry.

### Negative / trade-offs
- Two validation layers (model, then business rules) need clear boundaries.
- Naive timestamps are rejected, so a supplier that sends them needs a
  configured timezone (future work).

### Follow-ups
- Day 8 PR 2: synthetic supplier files.
- Next: extraction, validation and the quality gate.
