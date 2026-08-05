# ADR-009: Exception Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform executes multiple production data pipelines that interact with external sources, validate business information, transform data, and load results into storage systems.

During execution, failures can occur at different levels:

- External data sources may be unavailable.
- Input data may not respect expected business rules.
- Transformation logic may encounter unexpected conditions.
- Storage systems may reject operations.
- Configuration may be incomplete or invalid.

Without a consistent exception strategy, different components may handle failures in inconsistent ways.

Examples of problematic approaches include:

- Catching all exceptions without understanding their cause.
- Returning generic error messages that hide the origin of failures.
- Allowing low-level technical errors to leak into business logic.
- Logging the same error multiple times at different layers.
- Making pipeline failures difficult to diagnose.

The platform requires an exception strategy that provides:

- Clear failure classification.
- Meaningful error information.
- Separation between technical failures and business failures.
- Consistent handling across all pipelines.
- Compatibility with centralized logging and orchestration.

## Decision

The AGPP Data Platform adopts a centralized exception strategy.

Platform-level exceptions are defined under:

```text
src/shared/exceptions/
```

Exceptions are organized according to the layer and responsibility where failures occur.

The exception strategy follows these principles:

- Exceptions must represent meaningful failures, not generic programming errors.
- Each layer is responsible for raising exceptions related to its own responsibility.
- Low-level technical details should be wrapped into meaningful platform exceptions when crossing architectural boundaries.
- Exceptions must preserve the original cause of failures when applicable.
- Pipelines must not silently ignore failures.
- Error handling must allow orchestration systems to determine whether execution should retry, stop, or continue.

The exception categories follow the platform architecture:

```text
shared exceptions
        |
        +── Configuration errors
        |
        +── Data extraction errors
        |
        +── Validation errors
        |
        +── Transformation errors
        |
        +── Loading errors
        |
        +── Infrastructure errors
```

Examples:

### Configuration errors

Raised when required application configuration is missing or invalid.

Example:

- Missing database connection settings.

---

### Extraction errors

Raised when data cannot be retrieved from an external source.

Example:

- Source API unavailable.

---

### Validation errors

Raised when incoming data does not satisfy expected requirements.

Example:

- Missing mandatory supplier identifier.

---

### Transformation errors

Raised when valid data cannot be converted into the required internal representation.

Example:

- Invalid business calculation.

---

### Loading errors

Raised when processed data cannot be persisted.

Example:

- Warehouse insertion failure.

---

### Infrastructure errors

Raised when shared technical components fail.

Example:

- Database connection failure.

Pipeline-specific business exceptions remain inside the pipeline domain when they are not reusable platform concerns.

## Consequences

### Positive

- Provides consistent failure handling across the platform.
- Makes debugging and troubleshooting easier.
- Allows orchestration systems to react appropriately to different failure types.
- Separates business errors from technical failures.
- Improves log quality by providing meaningful failure context.
- Prevents silent failures that could corrupt business data.
- Creates a foundation for automated monitoring and alerting.

### Negative

- Requires additional design effort when introducing new failure scenarios.
- Poor exception classification can create unnecessary complexity.
- Developers must avoid creating overly generic exceptions.

### Neutral

- The internal exception hierarchy may evolve as the platform grows.
- Exception classes describe failure categories but do not replace logging or monitoring systems.
- Third-party library exceptions may still exist internally but should be translated when exposed across platform boundaries.
