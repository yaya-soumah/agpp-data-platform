# ADR-007: Shared Infrastructure Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform contains multiple independent business pipelines, including Supplier Products, Customer Orders, Inventory, Payments, Shipments, and Exchange Rates.

Although each pipeline owns its business logic, many technical capabilities are required across multiple parts of the platform.

Examples include:

- Database connections.
- Configuration loading.
- Logging.
- Date and time handling.
- Currency conversion.
- Common validation utilities.
- Error handling mechanisms.

Without a shared infrastructure strategy, each pipeline could implement its own version of these technical capabilities.

This would create:

- duplicated code,
- inconsistent behavior,
- different error handling approaches,
- difficult maintenance,
- increased operational complexity.

However, excessive sharing can also create problems. If business logic is placed into shared components, pipelines may become tightly coupled and lose ownership of their domain behavior.

The platform therefore needs a clear boundary between:

- reusable technical capabilities,
- pipeline-specific business logic.

## Decision

The AGPP Data Platform adopts a centralized shared infrastructure layer.

Generic technical capabilities used by multiple components belong under:

```text
src/shared/
```

The shared infrastructure layer contains reusable technical services, including:

```text
src/shared/
├── configuration/
├── database/
├── logging/
├── exceptions/
├── currency/
└── dates/
```

The following rules apply:

### Shared infrastructure may contain:

- Technical utilities.
- Cross-cutting services.
- Platform-level concerns.
- Reusable mechanisms required by multiple pipelines.

Examples:

- Loading configuration.
- Creating database connections.
- Standardizing logging.
- Handling common exceptions.
- Managing currency conversion rules.

---

### Shared infrastructure must not contain:

- Business-specific rules.
- Pipeline-specific transformations.
- Supplier logic.
- Order processing rules.
- Inventory calculations.

Business logic remains owned by its corresponding pipeline.

For example:

```text
Supplier product transformation
        ↓
src/pipelines/supplier_product/

Database connection handling
        ↓
src/shared/database/
```

The shared layer provides capabilities; it does not define business behavior.

## Consequences

### Positive

- Reduces duplication across pipelines.
- Ensures consistent technical behavior throughout the platform.
- Improves maintainability by centralizing cross-cutting concerns.
- Allows improvements to shared services to benefit all pipelines.
- Makes pipeline code focused on business responsibilities.
- Provides a clear ownership boundary between technical and business concerns.

### Negative

- Requires careful judgment to determine what belongs in shared infrastructure.
- Poorly designed shared components can become dependencies that slow development.
- Changes to shared components may affect multiple pipelines.

### Neutral

- A component should only move into shared infrastructure when it has a clear reuse purpose.
- Not every repeated piece of code automatically belongs in `shared/`.
- Future extraction of services from `shared/` remains possible if scaling requirements change.
