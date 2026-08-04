# ADR-006: Pipeline Architecture (Extract → Validate → Transform → Load)

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform processes data from multiple business sources and transforms it into reliable information for operational and analytical purposes.

As the number of business capabilities increases, each pipeline will need to perform similar categories of activities:

- Reading data from external sources.
- Checking whether incoming data is valid.
- Applying business transformations.
- Persisting processed results.

Without a standardized pipeline lifecycle, each business capability could evolve its own processing pattern. This would create inconsistent implementations, make maintenance difficult, and increase the learning curve for engineers working on the platform.

The platform requires a common pipeline architecture that provides:

- Predictable execution flow.
- Clear separation of responsibilities.
- Independent testing of each processing stage.
- Easier monitoring and troubleshooting.
- The ability to add new pipelines without redesigning the platform.

## Decision

The AGPP Data Platform adopts a standardized pipeline lifecycle:

```text
Extract
   ↓
Validate
   ↓
Transform
   ↓
Load
```

Every business pipeline must follow this structure.

Each pipeline is responsible for its own business domain and is isolated under:

```text
src/pipelines/
```

Example:

```text
src/pipelines/
├── supplier_product/
│   ├── extractor.py
│   ├── validator.py
│   ├── transformer.py
│   ├── loader.py
│   └── service.py
│
├── customer_orders/
├── inventory/
└── ...
```

Each stage has a clearly defined responsibility:

### Extract

Responsible for retrieving data from external sources.

Examples:

- Files
- APIs
- Databases
- External systems

The extraction layer should not contain business transformation rules.

---

### Validate

Responsible for ensuring incoming data satisfies expected quality and business requirements.

Examples:

- Required fields exist.
- Data types are correct.
- Business constraints are respected.

Invalid data must be handled according to the platform's data quality strategy.

---

### Transform

Responsible for converting validated data into the internal representation required by downstream systems.

Examples:

- Data normalization.
- Business calculations.
- Enrichment.
- Standardization.

Transformation logic belongs to the pipeline owning the business domain.

---

### Load

Responsible for persisting processed data into target storage systems.

Examples:

- Operational databases.
- Analytical warehouse.
- Data marts.

Loading logic must be separated from transformation logic.

---

Pipeline orchestration is handled externally and is not the responsibility of individual pipelines.

Pipelines expose executable interfaces but do not decide when or why they run.

## Consequences

### Positive

- Creates a consistent implementation pattern across all pipelines.
- Makes new pipelines easier to develop because the architecture is already defined.
- Allows engineers to understand any pipeline by knowing the standard lifecycle.
- Improves testing because each stage can be tested independently.
- Simplifies monitoring and troubleshooting by providing predictable execution stages.
- Reduces coupling between business logic and execution scheduling.
- Supports future orchestration tools without redesigning business logic.

### Negative

- Simple data flows may require additional structure compared with a quick script.
- Engineers must respect the separation between pipeline stages.
- Some complex scenarios may require careful design when responsibilities overlap.

### Neutral

- The internal implementation of each stage may evolve over time.
- Different pipelines may use different extraction or loading technologies while maintaining the same lifecycle.
- Additional stages may be introduced in the future if the platform requires them, but the existing lifecycle remains the foundation.
