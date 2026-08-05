# ADR-010: Testing Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform processes business-critical information through multiple independent pipelines, including Supplier Products, Customer Orders, Inventory, Payments, Shipments, and Exchange Rates.

As the platform grows, changes in one component may unintentionally affect other parts of the system. Without a structured testing strategy, regressions may be introduced silently, reducing confidence in deployments and slowing down development.

Traditional testing approaches that only verify the final output of an entire pipeline are insufficient because failures may originate from different layers:

- Business model validation.
- Data extraction.
- Transformation logic.
- Loading operations.
- Shared infrastructure.
- Pipeline orchestration.

The platform requires a testing strategy that enables engineers to:

- Verify individual components independently.
- Detect regressions early.
- Validate business rules.
- Safely evolve the platform.
- Maintain confidence during continuous development.

## Decision

The AGPP Data Platform adopts a layered testing strategy.

Every important component must be independently testable.

Tests are organized under:

```text
tests/
```

following the application architecture.

The testing strategy includes the following levels:

---

## Unit Tests

Unit tests verify individual components in isolation.

Examples:

- Business model validation.
- Transformation functions.
- Currency calculations.
- Date utilities.
- Configuration parsing.

Unit tests should be:

- Fast.
- Deterministic.
- Independent from external systems.

---

## Integration Tests

Integration tests verify that multiple components work correctly together.

Examples:

- Pipeline stages working together.
- Database interactions.
- Configuration loading.
- External service integrations.

Integration tests validate boundaries between components.

---

## Pipeline Tests

Pipeline tests verify complete business workflows.

Examples:

```text
Extract
   ↓
Validate
   ↓
Transform
   ↓
Load
```

A pipeline test confirms that a business capability behaves correctly from input data to final output.

---

## Data Quality Tests

Data quality checks verify that processed data satisfies business expectations.

Examples:

- Required fields are present.
- Duplicate records are detected.
- Financial values respect business constraints.
- Referential integrity is maintained.

---

## Testing Principles

The platform follows these principles:

- Every new feature must include appropriate tests.
- Tests must be maintainable and readable.
- Tests should verify behavior rather than implementation details.
- Business-critical transformations require strong test coverage.
- External dependencies should be isolated when testing business logic.
- Failed tests must provide enough information to diagnose the problem.

The testing strategy applies to all pipelines and shared infrastructure components.

## Consequences

### Positive

- Improves confidence when modifying existing functionality.
- Reduces regression risk as the platform grows.
- Encourages modular architecture because components must be independently testable.
- Makes debugging faster by identifying failures closer to their source.
- Supports automated CI/CD validation.
- Improves long-term maintainability.

### Negative

- Requires additional development effort.
- Poorly designed tests can become difficult to maintain.
- Test execution time may increase as the platform grows.

### Neutral

- Testing tools and frameworks may evolve without changing the architectural strategy.
- Not every component requires identical test coverage; testing depth depends on business impact and risk.
- Tests are part of the product lifecycle, not a separate activity performed after implementation.
