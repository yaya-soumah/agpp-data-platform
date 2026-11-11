# ADR-0016: Customer Orders pipeline contract

- **Status:** Accepted
- **Date:** 2026-11-09
- **Related decisions:** 06 (Business Models), 07 (Pipeline Flow),
  12 (Warehouse separation), 13 (Idempotency), 14 (Extensibility)

## Context

AGPP sells the products it buys from suppliers. The Customer Orders pipeline
loads order lines into the warehouse so that sales can be analysed by
customer, product and day. It is the second pipeline and must be added
without changing the Supplier Product pipeline (Decision 14).

## Decision

1. **Scope.** The pipeline owns customers and order lines. Products and
   suppliers belong to the Supplier Product pipeline.
2. **Input.** One order-lines CSV per run, at the path given in
   `config/pipelines/customer_orders.yaml`. One row is one order line:

   | Column | Type | Rule |
   |---|---|---|
   | `order_id` | text | required, 1-30 characters |
   | `line_number` | integer | required, >= 1 |
   | `customer_id` | text | required, `CUS-` followed by five digits |
   | `customer_name` | text | required, 1-200 characters |
   | `customer_country` | text | required, two capital letters |
   | `ordered_at` | timestamp | required, ISO 8601 with offset or `Z` |
   | `product_id` | text | required, `<supplier_id>:<supplier_sku>` |
   | `quantity` | integer | required, 1-10,000 |
   | `unit_price` | decimal | required, > 0, at most 4 decimal places |
   | `currency` | text | required, three letters |
   | `status` | text | required: `placed`, `shipped`, `delivered`, `cancelled` |
   | `updated_at` | timestamp | required, ISO 8601 with offset or `Z` |

3. **Parsing.** A Pydantic `OrderLine` model enforces types and ranges, trims
   text, upper-cases `product_id`, `currency` and `customer_country`,
   lower-cases `status`, and converts timestamps to UTC. Timestamps without an
   offset are rejected (as in ADR-0010).
4. **Business rules (configuration).** Allowed currencies; a maximum line
   amount (`quantity * unit_price`); `ordered_at` and `updated_at` not beyond
   the future tolerance; `updated_at` not before `ordered_at`; `ordered_at`
   within the calendar covered by `dim_date` (2000-2049).
5. **Duplicates.** Within the file, the key is `(order_id, line_number)`. The
   row with the latest `updated_at` is kept; on a tie, the later line.
6. **Unknown products are not rejects.** A line whose `product_id` is not (yet)
   in `dim_product` is loaded against the unknown member (`product_key = -1`,
   ADR-0009) and counted in the run summary. Orders can arrive before the
   catalog; rerunning the same file after the product appears corrects the
   reference, because the stored key then differs from the resolved one.
7. **Quality gate.** If rejected rows exceed `max_reject_ratio` of the file,
   nothing is loaded (`QualityThresholdExceededError`).
8. **Transformation.** `line_amount = quantity * unit_price`, fixed to four
   decimals; `order_date` is the UTC date of `ordered_at`; the customer name
   has repeated whitespace collapsed. Surrogate keys are resolved by the
   loader, not here (ADR-0013).
9. **Output (ADR-0009 conventions).**
   - `warehouse.dim_customer`: business key `customer_id`, name, country;
     Type 1; unknown member `-1`.
   - `warehouse.fact_order_line`: grain **one row per order line**; business key
     `(order_id, line_number)`; foreign keys `customer_key`, `product_key`,
     `date_key` (to `dim_date`); measures `quantity`, `unit_price`,
     `line_amount`; plus `currency`, `status`, `source_updated_at` and the
     audit columns. No currency conversion is done.
10. **Loading (ADR-0014).** One transaction per run: upsert customers, resolve
    customer and product keys, upsert order lines guarded by
    `source_updated_at`, store rejects, record the result. Lines absent from a
    later file are left alone; a failure rolls everything back.
11. **Independence.** The pipeline imports nothing from Supplier Product. The
    only link is data: it reads `warehouse.dim_product` to resolve keys. The
    Supplier Product pipeline should run first, and the unknown member makes a
    different order safe.
12. **Bookkeeping.** Runs use the shared `operational.pipeline_runs`; the
    pipeline owns its own result table (`operational.order_run_results`);
    rejects use the shared `operational.rejected_records` (ADR-0017).

## Consequences

### Positive
- A late catalog never blocks orders, and reruns heal unknown references.
- Fact rows are stable and idempotent like the dimensions.

### Negative / trade-offs
- Until the catalog arrives, some sales are attributed to "unknown product".
- The data dependency on `dim_product` must be documented for operators.

### Follow-ups
- Models, configuration, extraction, validation.
- Migrations, transformation and loading.
- Service, command, sample data and end-to-end tests.

## Amendments

- 2026-11-11: `dim_customer` also carries `source_updated_at`, so the guard of
  ADR-0014 (older data never overwrites newer data) applies to customers too.
  `fact_order_line` also carries `ordered_at`, keeping the time of day that
  `date_key` drops.
