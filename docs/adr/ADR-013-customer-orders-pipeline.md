# ADR-013: Customer Orders Pipeline Architecture

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform requires a Customer Orders pipeline to ingest and validate order data managed by AGPP's own operational Order Management System.

The pipeline must establish canonical domain representations for customers, orders, and order lines while reusing the existing Product domain and the platform's established pipeline architecture.

The operational system exports data as CSV. Unlike the Supplier Product pipeline, the Customer Orders pipeline does not need to demonstrate multiple extraction mechanisms. CSV is the selected source format for the initial implementation.

The source export consists of three related files:

- `customers.csv`
- `orders.csv`
- `order_lines.csv`

These files represent related entities from one authoritative operational system and must form one logically coherent export batch.

The pipeline must preserve the distinction between product information and transactional order information. In particular, the price associated with a supplier product is not necessarily the price agreed with a customer for an order line.

The implementation must follow the established AGPP architecture and remain independent of the eventual data warehouse integration.

## Decision

The Customer Orders pipeline will follow the established:

**Extract → Validate → Transform → Load**

lifecycle, using explicit stage contracts and dependency injection.

The canonical domain entities are:

- `Customer`
- `Order`
- `OrderLine`

The existing canonical Product identity will be referenced by order lines. The pipeline will not redefine the Product domain.

### 1. Source and extraction boundary

The authoritative source is AGPP's Order Management System.

The initial source contract consists of three CSV files.

| File              | Grain                  | Purpose                                             |
| ----------------- | ---------------------- | --------------------------------------------------- |
| `customers.csv`   | One row per customer   | Customer records                                    |
| `orders.csv`      | One row per order      | Order headers                                       |
| `order_lines.csv` | One row per order line | Products, quantities, and transactional unit prices |

The extraction layer obtains the files and converts their contents into pipeline records.

Extraction must not perform domain transformation or business validation.

The initial implementation will use a CSV extractor. API and FTP extractors are not part of this pipeline's scope.

The three files constitute one logical export batch. The pipeline must not treat an incomplete or demonstrably inconsistent export as a complete dataset.

### 2. Domain model boundary

Pydantic is the standard for AGPP domain models and validation.

#### Customer

A `Customer` represents a business customer managed by AGPP.

Initial fields:

- `customer_id`: AGPP-owned unique business identifier.
- `name`: Customer's business name.

Additional customer attributes will be introduced only when supported by a concrete requirement.

#### Order

An `Order` represents a customer's request to purchase one or more products.

Initial fields:

- `order_id`: AGPP-owned unique business identifier.
- `customer_id`: Identifier of the customer placing the order.
- `ordered_at`: Timestamp when the order was placed.
- `status`: Current order lifecycle status.
- `cancelled_at`: Optional cancellation timestamp, subject to the source contract.

The initial lifecycle supports `PLACED` and `CANCELLED`.

Cancellation does not delete the order or its lines. Line-level cancellation and fulfilment states are outside the initial scope.

#### OrderLine

An `OrderLine` represents one product occurrence within an order.

Initial fields:

- `order_line_id`: AGPP-owned unique business identifier.
- `order_id`: Identifier of the parent order.
- `product_id`: Existing canonical Product identifier.
- `quantity`: Ordered quantity.
- `unit_price_amount`: Transactional unit-price amount.
- `unit_price_currency`: Currency of the transactional unit price.

The domain models will follow established AGPP Pydantic conventions, including strict validation, rejection of unexpected fields, and assignment validation where appropriate.

Source-specific representations must not leak into the canonical domain models.

### 3. Identity and relationship contract

AGPP owns the canonical business identifiers for customers, orders, and order lines.

- `customer_id` uniquely identifies a customer within AGPP.
- `order_id` uniquely identifies an order within AGPP.
- `order_line_id` uniquely identifies an order line within AGPP.
- `product_id` references the existing canonical Product identity.

Source-system identifiers, if subsequently required for lineage, must not replace these business identifiers.

Warehouse surrogate keys belong to the warehouse integration design and must not be confused with operational business identifiers.

The required relationships are:

- One customer can have many orders.
- Every order belongs to exactly one customer.
- Every order contains at least one order line.
- Every order line belongs to exactly one order.
- Every order line references exactly one existing product.

### 4. Validation boundary

Validation is responsible for structural, field-level, business, and cross-file integrity checks.

Pydantic will validate the applicable record and domain-model constraints.

Validation must cover:

- Required fields and permitted field types.
- Unique business identifiers.
- Valid order statuses.
- Positive order-line quantities.
- Non-negative transactional unit prices.
- Valid currency representation.
- Customer, order, and product references.
- Completeness of each accepted order.

Cross-file validation must ensure that an order references a known customer, each order line references a known order and product, and each accepted order has at least one line.

The validation layer must distinguish record-level errors from business-entity integrity failures and batch-level failures.

An order with invalid or incomplete line data must not be accepted as a complete order. Independent valid orders may continue to be processed when batch integrity is reliable.

A missing required file, missing required header, or export whose completeness cannot be established must fail the batch.

Validation must preserve rejection reasons and counts. It must not silently repair data, choose arbitrarily between conflicting duplicate records, or silently discard invalid records.

A maximum rejection ratio will be established only when its denominator and business meaning are explicitly defined.

### 5. Transformation boundary

Transformation converts validated pipeline records into canonical AGPP domain models:

- `Customer`
- `Order`
- `OrderLine`

The transformation stage must not perform persistence.

The existing Supplier Product domain and canonical Product identity remain authoritative for product information.

### 6. Price semantics

Supplier Product pricing and Customer Order Line pricing represent different business facts.

The Supplier Product price represents the applicable supplier/product commercial price.

The Order Line's `unit_price_amount` and `unit_price_currency` represent the transactional unit price agreed with the customer for that order line.

The order-line price must remain independent of subsequent changes to the supplier/product price.

The existing `Price` value object is not required for this implementation. The pipeline will follow the established approach of using explicit Pydantic fields for amount and currency.

The line total is derived from quantity and unit price:

```
line_total = quantity × unit_price_amount
```

The derived total must retain the unit-price currency. Currency conversion and additional financial calculations are outside this initial domain-model decision.

### 7. Lifecycle semantics

The initial order statuses are:

- `PLACED`: The order has been submitted and recorded.
- `CANCELLED`: The order has been cancelled.

Cancellation is terminal in the initial lifecycle. Reinstatement, partial cancellation, fulfilment, shipment, and payment states are not included.

The exported status represents the current state reported by the operational system. A CSV snapshot alone does not establish the complete sequence of historical status transitions.

The pipeline must not invent a cancellation timestamp when the source does not provide one.

### 8. Loading boundary

The loader receives canonical domain models and persists them through an explicit contract.

The loader must not perform extraction, business validation, or domain transformation.

The initial implementation must not depend on the data warehouse or introduce fact-table integration. The concrete persistence destination and warehouse integration remain subject to the planned implementation phases.

Loading behavior must preserve the integrity of accepted business entities and must not leave an order partially persisted without an explicitly defined recovery strategy.

### 9. Pipeline orchestration

`CustomerOrdersPipelineService` coordinates the pipeline stages through dependency injection.

Conceptually:

```
CustomerOrdersPipelineService
    │
    ├── Extractor
    ├── Validator
    ├── Transformer
    └── Loader
```

The service coordinates execution but does not contain the individual stages' business logic.

The service must not construct concrete stage implementations internally.

### 10. Contract-based dependencies

The pipeline will define explicit contracts for:

- `CustomerOrdersExtractor`
- `CustomerOrdersValidator`
- `CustomerOrdersTransformer`
- `CustomerOrdersLoader`

The concrete CSV extraction implementation will satisfy the extractor contract.

The initial implementation will use collection-based processing, consistent with the existing AGPP architecture. Streaming and chunking will be reconsidered when actual data-volume requirements justify them.

### 11. Error propagation

The pipeline will use the existing AGPP exception hierarchy.

Expected error mapping:

- Extraction → `DataExtractionError`
- Validation → `ValidationError`
- Transformation → `TransformationError`
- Loading → `LoadingError`

The pipeline service must not catch generic exceptions merely to conceal or replace them.

Stage failures propagate to the caller/orchestration layer. Retry decisions remain an orchestration responsibility and must follow the existing exception retryability contract.

### 12. Configuration and observability

Pipeline components will receive only the configuration required for their responsibilities.

The pipeline will use AGPP's established logging and configuration infrastructure.

Operational logs and pipeline results must make extraction failures, rejected records, invalid orders, batch failures, and loading outcomes observable without silently discarding the underlying cause.

## Consequences

### Positive consequences

**Consistent architecture**

The Customer Orders pipeline follows the same lifecycle and stage boundaries as the Supplier Product pipeline.

**Clear domain ownership**

Customer, Order, and OrderLine have explicit business identities and responsibilities.

**Reliable transactional pricing**

Order-line prices preserve the customer transaction price independently of changes to supplier/product pricing.

**Data integrity**

Cross-file validation protects customer/order/product relationships and prevents incomplete orders from being treated as valid.

**Testability**

Each stage can be tested independently, and the orchestration service can be tested using injected test doubles.

**Warehouse independence**

The domain implementation can be completed without prematurely coupling it to warehouse fact tables.

### Negative consequences

**Multiple source files**

The pipeline must coordinate three related CSV files and validate cross-file references and completeness.

**Additional data representations**

Raw records, validated records, and canonical domain models introduce more contracts and transformation steps.

**Initial collection-based processing**

Loading complete collections may increase memory usage for large exports. This is accepted until actual volume requirements establish the need for chunking or streaming.

**Explicit rejection handling**

The pipeline requires a defined strategy for reporting and isolating invalid orders instead of treating every row independently.

## Rejected Alternatives

### 1. One monolithic pipeline class

**Rejected because:** it couples extraction, validation, transformation, and loading, making individual responsibilities harder to test and replace.

### 2. Reusing the supplier/product price for order lines

**Rejected because:** the supplier/product price and the customer transaction price represent different business facts. Historical order pricing must not change when the supplier/product price changes.

### 3. A single flattened CSV as the canonical domain representation

**Rejected because:** a flattened source representation should not determine the domain model. The selected source contract separates customer, order, and order-line records while preserving their relationships.

### 4. Reimplementing API and FTP extraction

**Rejected because:** those extraction mechanisms have already been demonstrated in the Supplier Product pipeline and are not required for the selected Customer Orders source.

### 5. Introducing warehouse facts during domain implementation

**Rejected because:** warehouse fact design depends on concrete business domains and their stable contracts. It belongs to the later warehouse-completion phase.

### 6. Introducing speculative customer, order, and fulfilment fields

**Rejected because:** additional attributes and lifecycle states must be justified by actual business requirements rather than anticipated future features.

## Implementation Plan

The implementation will follow the established AGPP development workflow.

| Sprint    | Responsibility                               |
| --------- | -------------------------------------------- |
| Sprint 31 | Business analysis and domain contract        |
| Sprint 32 | Customer, Order, and OrderLine domain models |
| Sprint 33 | Customer Orders pipeline implementation      |
| Sprint 34 | Order calculations                           |
| Sprint 35 | Customer Orders warehouse integration        |

The implementation must pass all four established quality gates:

```
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Implementation references will be assigned only after the relevant implementation has been completed, tested, reviewed, corrected, merged, and established as the authoritative version.

## Related Decisions

- ADR-005 — Business Model Strategy
- ADR-006 — Pipeline Architecture
- ADR-007 — Shared Infrastructure
- ADR-008 — Logging Strategy
- ADR-009 — Exception Strategy
- ADR-010 — Testing Strategy
- ADR-011 — Runtime Environment Resolution
- ADR-012 — Supplier Product Pipeline Architecture