# ADR-008: Logging Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform executes production data pipelines that process business-critical information, including supplier data, customer orders, inventory movements, financial transactions, and operational events.

In a production environment, pipeline failures, unexpected data conditions, performance issues, and operational events must be observable and diagnosable.

Without a consistent logging strategy, different components may produce inconsistent messages, insufficient operational information, or uncontrolled output.

Examples of poor logging practices include:

- Using standard output statements for operational information.
- Logging sensitive information.
- Producing messages without timestamps or execution context.
- Using different logging formats across pipelines.
- Making failures difficult to trace after execution.

The platform requires a centralized logging approach that allows engineers to understand:

- What happened?
- When did it happen?
- Which pipeline component produced the event?
- Which execution was affected?
- Why did a failure occur?

## Decision

The AGPP Data Platform adopts a centralized logging strategy.

All application logging must use the shared logging infrastructure located under:

```text
src/shared/logging/
```

Direct use of basic output statements for operational logging is not permitted.

Logging follows these principles:

- Every important pipeline execution event must be logged.
- Logging must be consistent across all pipelines.
- Logs must include enough contextual information for troubleshooting.
- Log levels must reflect the severity and purpose of events.
- Sensitive information must never be written to logs.
- Logging configuration must be externalized and environment-specific.

The platform uses standard log levels:

### DEBUG

Used for detailed diagnostic information during development or troubleshooting.

Examples:

- Intermediate processing details.
- Internal state information.

---

### INFO

Used for normal operational events.

Examples:

- Pipeline started.
- Extraction completed.
- Records successfully loaded.

---

### WARNING

Used when execution can continue but attention may be required.

Examples:

- Unexpected but recoverable data conditions.
- Deprecated configuration usage.

---

### ERROR

Used when an operation fails but the application can continue or recover.

Examples:

- Individual record processing failure.
- External service unavailable temporarily.

---

### CRITICAL

Used for failures that prevent normal platform operation.

Examples:

- Application startup failure.
- Database unavailable during required operations.

---

Logging configuration is separated from application code and managed through the configuration layer defined in ADR-003.

Example:

```text
config/
└── logging.yaml
```

Pipeline components are responsible for emitting meaningful events, while the shared logging layer is responsible for formatting, routing, and managing log output.

## Consequences

### Positive

- Provides consistent observability across all pipelines.
- Makes production troubleshooting faster and more reliable.
- Allows centralized changes to logging behavior without modifying business logic.
- Supports future integration with monitoring and observability platforms.
- Improves operational confidence when running automated pipelines.
- Creates a clear audit trail of platform activity.

### Negative

- Requires engineers to design meaningful logging messages.
- Excessive logging can increase storage requirements and reduce signal-to-noise ratio.
- Logging sensitive data requires continuous attention and discipline.

### Neutral

- The underlying logging technology may evolve without changing the architectural decision.
- Different environments may use different logging configurations while following the same strategy.
- Logs are operational artifacts and do not replace proper monitoring, metrics, or data quality reporting.
