# ADR-002: Project Structure

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform is a long-lived production project expected to evolve by adding new business capabilities over time, including Supplier Products, Customer Orders, Inventory, Payments, Shipments, and Exchange Rates.

As the platform grows, the number of source files, shared components, tests, configuration files, SQL scripts, and documentation will increase significantly. Without a well-defined project structure, the repository would become difficult to navigate, increase coupling between components, and make onboarding new contributors unnecessarily complex.

The project structure must therefore support:

- Separation of business domains.
- Reuse of common infrastructure.
- Independent development and testing of pipelines.
- Clear ownership of responsibilities.
- Scalability as new business capabilities are introduced.
- Consistent organization across the entire repository.

The repository structure should communicate the architecture of the platform without requiring contributors to study the implementation.

## Decision

The AGPP Data Platform adopts a layered directory structure that separates business capabilities from shared infrastructure.

Business functionality is organized into independent pipelines under `src/pipelines/`, where each pipeline owns its business logic and follows a common lifecycle.

Cross-cutting technical components that are shared across multiple pipelines are centralized under `src/shared/`.

Business concepts are represented by domain models under `src/models/`.

Analytical storage components are isolated under `src/warehouse/`.

Configuration, documentation, SQL assets, test suites, datasets, and operational artifacts each have dedicated top-level directories outside the application source code.

The project structure is defined as follows:

```text
agpp-data-platform/
├── .venv/
├── .env
├── .env_example
├── src/
│   ├── pipelines/
│   │   ├── supplier_product/
│   │   ├── customer_orders/
│   │   ├── inventory/
│   │   └── ...
│   ├── models/
│   ├── shared/
│   │   ├── configuration/
│   │   ├── database/
│   │   ├── logging/
│   │   ├── exceptions/
│   │   ├── currency/
│   │   └── dates/
│   ├── warehouse/
│   └── main.py
├── tests/
├── config/
├── data/
├── docs/
├── logs/
├── sql/
├── README.md
├── pyproject.toml
├── requirements.txt
└── .gitignore
```

Future business capabilities will be added by creating new pipeline directories under `src/pipelines/` without modifying the overall project organization.

## Consequences

### Positive

- Provides a predictable and consistent repository layout.
- Clearly separates business logic from technical infrastructure.
- Encourages modular development and low coupling.
- Makes onboarding easier by giving contributors a logical project organization.
- Simplifies navigation as the platform grows.
- Supports independent testing of business capabilities.
- Allows new pipelines to be introduced with minimal impact on existing components.
- Keeps documentation, configuration, SQL, and operational assets organized and discoverable.

### Negative

- Requires discipline to maintain architectural boundaries.
- Contributors must understand the responsibility of each directory before introducing new components.
- Refactoring may be required if responsibilities evolve significantly over time.

### Neutral

- The directory structure reflects the platform architecture rather than deployment boundaries.
- Empty directories may exist during early development until their corresponding capabilities are implemented.
- The structure is intended to remain stable throughout the lifetime of the project, even as new business capabilities are added.
