# ADR-005: Business Model Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform processes business information generated from multiple operational domains, including suppliers, products, customer orders, inventory, shipments, invoices, payments, and exchange rates.

These business entities represent real-world concepts that must be understood consistently across the platform. If each pipeline defines its own interpretation of the same business concept, inconsistencies will appear over time.

For example:

- A supplier identifier may be represented differently in different pipelines.
- Product information may contain inconsistent fields depending on the data source.
- Financial values may be handled differently between operational processes.
- Business rules may become duplicated across multiple pipelines.

The platform therefore requires a consistent way to represent business concepts independently from data sources and technical implementation details.

The solution must support:

- Clear business ownership of data concepts.
- Validation of incoming data.
- Reuse across multiple pipelines.
- Evolution of business rules over time.
- Separation between raw external data and trusted internal representations.

## Decision

The AGPP Data Platform adopts a **centralized business model strategy**.

Business concepts are represented as explicit domain models under:

```text
src/models/
```

Examples:

```text
src/models/
├── supplier.py
├── order.py
├── inventory.py
└── ...
```

Each model represents a business entity or value object used throughout the platform.

The business models follow these principles:

- Business concepts are modeled explicitly rather than represented as unstructured dictionaries.
- Models define the expected structure and rules of business data.
- Validation occurs at the boundary where external data enters the platform.
- Pipelines consume validated business models rather than raw source structures whenever possible.
- Business models are independent from storage implementation.
- Database schemas and analytical models are derived from business concepts but are not identical to them.

Business models represent the meaning of data, while pipelines represent the processing workflow.

## Consequences

### Positive

- Creates a single understanding of business concepts across the platform.
- Reduces duplication of business rules between pipelines.
- Improves data quality by validating information early.
- Makes pipelines easier to test because they operate on well-defined objects.
- Allows business rules to evolve independently from external data formats.
- Improves communication between engineering and business stakeholders.
- Provides a foundation for consistent warehouse modeling.

### Negative

- Requires additional design effort before implementing new business capabilities.
- Business models must evolve carefully to avoid breaking dependent pipelines.
- Incorrect abstraction of business concepts can introduce unnecessary complexity.

### Neutral

- Business models do not represent database tables directly.
- Different storage systems may use different representations while still relying on the same business concepts.
- Some source-specific fields may exist outside the core business models if they do not represent universal business meaning.
