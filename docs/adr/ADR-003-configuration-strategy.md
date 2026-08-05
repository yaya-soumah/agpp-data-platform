# ADR-003: Configuration Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform is expected to operate across multiple environments throughout its lifecycle, including local development, testing, staging, and production.

Each environment requires different operational settings, such as database connections, logging levels, file locations, feature flags, and external service endpoints. Hardcoding these values into the application would tightly couple the software to a specific environment, making deployments error-prone and reducing maintainability.

The platform must therefore provide a configuration mechanism that allows behavior to be modified without changing application code.

Additionally, configuration should remain understandable, version-controlled when appropriate, and easily extendable as new pipelines and infrastructure components are introduced.

## Decision

The AGPP Data Platform adopts a **configuration-first** architecture.

Application behavior must be driven by external configuration files rather than hardcoded values.

Configuration files are stored under the `config/` directory and are organized by execution environment.

```text
config/
├── base.yaml
├── development.yaml
├── testing.yaml
└── production.yaml
```

The configuration strategy follows these principles:

- `base.yaml` contains configuration shared by all environments.
- Environment-specific configuration files override only the values that differ from the base configuration.
- Business logic must never contain environment-specific values.
- Configuration is loaded during application startup and made available to the rest of the platform through a centralized configuration component.
- Pipelines consume configuration but never determine how configuration is loaded.
- Configuration files are version-controlled because they describe the behavior of the platform rather than sensitive information.

Sensitive information, such as passwords, API keys, and access tokens, is **not** stored in configuration files. Secret management is addressed separately in **ADR-004: Environment Variable Strategy**.

## Consequences

### Positive

- Separates application behavior from application code.
- Simplifies deployment across multiple environments.
- Reduces the risk of environment-specific bugs.
- Allows operational changes without modifying source code.
- Encourages consistency across all pipelines.
- Makes configuration changes visible through version control.
- Supports future expansion as new pipelines and infrastructure components are added.

### Negative

- Introduces an additional layer that must be maintained.
- Incorrect or incomplete configuration files can prevent the application from starting.
- Contributors must understand the configuration hierarchy before introducing new settings.

### Neutral

- The configuration format is an implementation detail and may evolve without changing the architectural decision.
- Additional environment profiles may be introduced as deployment requirements evolve.
- Configuration loading is centralized, allowing the remainder of the application to remain independent of configuration sources.
