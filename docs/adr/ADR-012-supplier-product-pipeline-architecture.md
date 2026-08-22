# ADR-012: Supplier Product Pipeline Architecture

* **Status:** Accepted
* **Date:** 2026-08-22
* **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform will contain multiple business pipelines, including Supplier Product, Customer Orders, Inventory, Payments, Shipments, and Exchange Rates.

Each pipeline interacts with external data sources, validates incoming data, transforms it into AGPP domain models, and persists the resulting data.

Without a consistent pipeline architecture, individual pipelines could develop different execution flows and responsibilities. This would make the platform harder to understand, test, extend, and maintain.

The Supplier Product pipeline is the first pipeline implementation and therefore establishes the architectural pattern that future pipelines should follow.

The architecture must also allow individual pipeline stages to evolve independently. In particular, the extraction mechanism must be replaceable because supplier data may eventually originate from CSV files, APIs, FTP sources, or other mechanisms.

The pipeline must therefore separate:

* external data acquisition;
* validation;
* transformation into domain models;
* persistence;
* orchestration of these stages.

## Decision

AGPP pipelines will follow a standardized:

**Extract → Validate → Transform → Load**

lifecycle.

Each stage will expose an explicit contract, and the pipeline service will orchestrate these stages through dependency injection.

The Supplier Product pipeline therefore has the following logical structure:

```text
                 SupplierProductPipelineService
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
          Extractor        Validator       Transformer
              │               │                │
              ▼               ▼                ▼
         Raw Record      Validated Record   SupplierProduct
                                                │
                                                ▼
                                             Loader
                                                │
                                                ▼
                                           LoadResult
```

### 1. Extraction boundary

The extractor is responsible only for obtaining supplier product records from an external source.

The pipeline defines an extraction contract independent of the concrete source.

Future implementations may include:

```text
CSVExtractor
APIExtractor
FTPExtractor
```

The pipeline service must not depend on any specific extraction mechanism.

### 2. Validation boundary

Validation receives pipeline records produced by the extractor and produces validated records.

Validation is responsible for determining whether incoming data satisfies the required structural and business rules.

Validation does not transform source representations into canonical domain representations.

### 3. Transformation boundary

Transformation converts validated pipeline records into AGPP domain models.

For the Supplier Product pipeline, the canonical output is:

```text
SupplierProduct
```

The existing `SupplierProduct` model therefore represents the **domain boundary** of the pipeline.

Source-specific representations must not leak into the domain model.

For example, source-level price and currency information may be converted into the existing `Money` domain type during transformation.

### 4. Loading boundary

The loader receives domain models and persists them.

The loader must not be responsible for:

* extraction;
* business validation;
* domain transformation.

This ensures that persistence mechanisms can change without changing upstream business processing.

### 5. Pipeline orchestration

`SupplierProductPipelineService` coordinates the four stages.

It receives stage implementations through dependency injection rather than constructing concrete implementations internally.

Conceptually:

```text
PipelineService
    │
    ├── Extractor
    ├── Validator
    ├── Transformer
    └── Loader
```

The service coordinates execution but does not contain the business logic of individual stages.

### 6. Contract-based dependencies

Pipeline stages are defined through contracts rather than concrete implementations.

This allows different implementations to satisfy the same pipeline architecture and makes each component independently testable.

For example:

```text
Extractor
   ▲
   ├── CSVExtractor
   ├── APIExtractor
   └── FTPExtractor
```

Adding a new extraction mechanism should not require modifying the pipeline service.

### 7. Error propagation

Pipeline stages use the existing AGPP exception hierarchy.

The expected mapping is:

```text
Extractor   → DataExtractionError
Validator   → ValidationError
Transformer → TransformationError
Loader      → LoadingError
```

The pipeline service does not catch generic exceptions merely to conceal or replace them.

Stage failures propagate to the caller/orchestration layer.

Retry decisions remain an orchestration concern and are not implemented inside individual pipeline stages.

### 8. Configuration dependency

Pipeline components must not depend unnecessarily on the complete application `Configuration` object.

They should receive only the configuration required for their responsibility.

Pipeline-level configuration such as `batch_size` and retry policy remains part of the existing configuration architecture and will be applied where the corresponding operational responsibility is established.

### 9. Collection-based contracts

The initial Supplier Product pipeline contracts operate on collections of records:

```text
Sequence[SupplierProductRecord]
Sequence[ValidatedSupplierProductRecord]
Sequence[SupplierProduct]
```

Streaming or iterator-based processing is intentionally not introduced at this stage.

The existing `batch_size` configuration provides a future mechanism for controlled processing as extraction and loading requirements become concrete.

Batching and streaming decisions will be revisited when actual source and persistence requirements are implemented.

## Consequences

### Positive consequences

#### Consistent architecture

Future AGPP pipelines can follow the same lifecycle:

```text
Extract
   ↓
Validate
   ↓
Transform
   ↓
Load
```

This creates a predictable platform-wide architecture.

#### Replaceable infrastructure

The Supplier Product pipeline can change from:

```text
CSV → PostgreSQL
```

to:

```text
API → PostgreSQL
```

without changing the pipeline's core orchestration architecture.

#### Improved testability

Each stage can be tested independently.

The pipeline service can also be tested using test doubles for each stage without requiring external systems.

#### Clear domain boundary

The `SupplierProduct` model becomes the canonical business representation rather than allowing source-specific structures to propagate through the platform.

#### Separation of concerns

External-system concerns remain separated from:

* validation;
* domain transformation;
* persistence;
* orchestration.

#### Extensibility

Adding another implementation of an existing stage should not require modification of existing pipeline logic.

This supports the previously established AGPP extensibility decision.

### Negative consequences

#### More abstractions

The architecture introduces explicit contracts and intermediate data models instead of passing dictionaries directly between stages.

This creates additional code and concepts.

The additional complexity is accepted because the repository is intended to represent a production-grade data platform rather than a one-off script.

#### Additional data representations

A record may exist in several representations during execution:

```text
RawSupplierProductRecord
        ↓
ValidatedSupplierProductRecord
        ↓
SupplierProduct
```

This introduces transformation overhead and requires maintaining multiple contracts.

The separation is accepted because each representation has a distinct architectural responsibility.

#### Initial collection-based processing

The current contracts operate on collections rather than streams.

For very large datasets this may create memory pressure.

This is accepted for the initial architecture and will be reconsidered when real extraction and loading requirements establish whether streaming or chunked processing is necessary.

## Rejected Alternatives

### 1. One monolithic pipeline class

```text
SupplierProductPipeline
    └── extract + validate + transform + load
```

**Rejected because:** it tightly couples unrelated responsibilities, makes testing harder, and prevents independent replacement of pipeline stages.

### 2. Extractor performs validation

```text
Extractor
    └── extract + validate
```

**Rejected because:** extraction and validation have different responsibilities. It would also make different extraction mechanisms responsible for implementing the same validation rules.

### 3. Validator produces `SupplierProduct` directly

```text
Raw Record
    ↓
Validator
    ↓
SupplierProduct
```

**Rejected because:** validation and domain transformation become coupled. Source representation changes, such as converting price/currency into `Money`, belong to transformation.

### 4. Loader performs transformation

```text
Validated Record
    ↓
Loader
    ├── transform
    └── persist
```

**Rejected because:** persistence concerns would become coupled to business transformation.

### 5. Pipeline service constructs concrete implementations

```text
SupplierProductPipelineService
    └── CSVExtractor()
    └── SupplierProductValidator()
    └── ...
```

**Rejected because:** this creates tight coupling and makes testing and replacing implementations more difficult.

Dependency injection is therefore preferred.

## Implementation

The Supplier Product pipeline introduces the following contracts:

```text
SupplierProductExtractor
SupplierProductValidator
SupplierProductTransformer
SupplierProductLoader
```

and the orchestration service:

```text
SupplierProductPipelineService
```

Pipeline-specific records are represented separately from domain models:

```text
SupplierProductRecord
ValidatedSupplierProductRecord
```

The canonical domain output remains:

```text
SupplierProduct
```

Concrete implementations are intentionally deferred to later sprints:

| Sprint    | Responsibility         |
| --------- | ---------------------- |
| Sprint 17 | CSV Extract Layer      |
| Sprint 18 | API Extract Layer      |
| Sprint 19 | FTP Extract Layer      |
| Sprint 20 | Schema Validation      |
| Sprint 21 | Business Validation    |
| Sprint 23 | Data Transformation    |
| Sprint 26 | PostgreSQL Loader      |
| Sprint 27 | Warehouse Loader       |
| Sprint 28 | Pipeline Orchestration |

## Related Decisions

* **ADR-005** — Business Model Strategy
* **ADR-006** — Pipeline Architecture
* **ADR-007** — Shared Infrastructure
* **ADR-008** — Logging Strategy
* **ADR-009** — Exception Strategy
* **ADR-010** — Testing Strategy
* **ADR-011** — Runtime Environment Resolution
