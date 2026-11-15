# ADR-0018: Inventory pipeline contract

- **Status:** Accepted
- **Date:** 2026-11-13
- **Related decisions:** 05 (Environment variables), 06 (Business Models),
  07 (Pipeline Flow), 12 (Warehouse separation), 13 (Idempotency),
  14 (Extensibility)

## Context

AGPP holds stock in several locations (warehouses). A stock service publishes
the current levels as a JSON feed over HTTP. The Inventory pipeline loads them
so that stock can be analysed by location, product and day. It is the third
pipeline and the first with a non-file source; it must not change the other two.

## Decision

1. **Scope.** The pipeline owns locations and stock levels. Products belong to
   the Supplier Product pipeline.
2. **Source.** `source.type: api` in `config/pipelines/inventory.yaml`. The
   feed is read with `GET <base_url><path>?page=N&page_size=M`. A page is a JSON
   object:

   ```json
   {"snapshot_at": "2026-11-13T06:00:00Z", "items": [ ... ], "next_page": 2}
   ```

   Pages start at 1; `next_page` is `null` on the last page. Every page of one
   read must report the same `snapshot_at`; a change means the feed moved while
   it was being read, which is retryable (`SourceUnavailableError`).
3. **Items.** Each item is a JSON object:

   | Field | Type | Rule |
   |---|---|---|
   | `location_code` | text | required, two letters, a dash, two digits |
   | `location_name` | text | required, 1-200 characters |
   | `location_country` | text | required, two capital letters |
   | `product_id` | text | required, `<supplier_id>:<supplier_sku>` |
   | `on_hand` | integer | required, 0-1,000,000 |
   | `reserved` | integer | required, 0-1,000,000 |
   | `reorder_point` | integer | required, 0-1,000,000 |
   | `updated_at` | timestamp | required, ISO 8601 with offset or `Z` |

4. **Access and secrets.** The token is a bearer token taken from the
   environment through a configuration placeholder, held as a secret value, and
   never logged or placed in an error. Timeouts and page size are configuration.
5. **HTTP errors** (ADR-0011): a network failure, timeout, `429` or `5xx` raises
   `SourceUnavailableError` (retryable); any other non-success status, invalid
   JSON or an unexpected page shape raises `ExtractionError`. A feed that never
   ends (too many pages, or a `next_page` that does not advance) raises
   `ExtractionError`.
6. **From JSON to records.** Items become the same `RawRecord` as file rows, so
   validation works on text values: numbers and booleans become text, `null`
   becomes blank, and a nested value or a non-object item is flagged on the
   record. The "line number" of a record is its 1-based position in the feed.
7. **Parsing.** An `InventoryItem` model enforces types and ranges, upper-cases
   `location_code`, `location_country` and `product_id`, and converts timestamps
   to UTC.
8. **Business rules.** `reserved` must not exceed `on_hand`; `updated_at` must
   not be after `snapshot_at` plus the future tolerance. At feed level the
   snapshot must not be older than `max_snapshot_age_hours` nor in the future
   (`InvalidSnapshotError`).
9. **Duplicates.** The key is `(location_code, product_id)`; the latest
   `updated_at` wins, the later item on a tie.
10. **Quality gate.** As in ADR-0010: too many rejects stops the run.
11. **Transformation.** `available = on_hand - reserved`;
    `below_reorder_point = available < reorder_point`; the snapshot date is the
    UTC date of `snapshot_at`. Surrogate keys are resolved by the loader.
12. **Output (ADR-0009 conventions).**
    - `warehouse.dim_location`: business key `location_code`, name, country;
      Type 1; unknown member `-1`.
    - `warehouse.fact_inventory_snapshot`, a **periodic snapshot**: grain one row
      per location, product and snapshot date; business key
      `(date_key, location_key, product_id)`; foreign keys `location_key`,
      `product_key` and `date_key`; measures `on_hand`, `reserved`, `available`,
      `reorder_point`, `below_reorder_point`; plus `snapshot_at`,
      `source_updated_at` and the audit columns. `product_id` stays on the fact
      so that different unknown products remain distinct rows.
13. **Snapshot semantics.** Running again on the same day updates that day's rows
    (newest data wins, ADR-0014); a new day adds new rows, which is the history.
    An item missing from the feed is left alone: a zero must be sent explicitly.
14. **Unknown products** load against the unknown member and heal on rerun,
    exactly as in ADR-0016.
15. **Loading** follows ADR-0014 and ADR-0016: one transaction per run, shared
    run bookkeeping and reject storage, and its own result table
    (`operational.inventory_run_results`).
16. **Independence.** Inventory imports nothing from the other pipelines; the
    only link is the data in `dim_product`. There is no extractor registry,
    because there is one source type (ADR-0017).

## Consequences

### Positive
- Stock history by day, location and product, with the same idempotent loading.
- The HTTP building block is reusable by any later API source.

### Negative / trade-offs
- Snapshots grow by one row per location and product per day.
- Missing items are never zeroed automatically; the source must send zeros.

### Follow-ups
- Day 18 PR 2: the shared API reader.
- Day 19: extraction and validation. Day 20: tables, transformation, loading.
- Day 21: service, a local mock feed, commands and end-to-end tests.
