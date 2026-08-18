# ADR-011: Runtime Environment Resolution

- **Status:** Accepted
- **Date:** 2026-08-17
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform operates across multiple execution environments, including development, testing, and production.

The platform already defines these environments through the `Environment` enum:

- `development`
- `testing`
- `production`

Application configuration is stored in environment-specific YAML files according to ADR-003.

The configuration service currently requires the caller to explicitly provide an `Environment` value when loading configuration.

While this provides a deterministic configuration service API, the application must also determine which environment it is running in without hardcoding the environment in application code.

Hardcoding an environment would make the application coupled to a specific deployment environment and would require source-code changes when deploying the same application to another environment.

The platform therefore needs a runtime mechanism for selecting the active execution environment.

## Decision

The AGPP Data Platform will determine its active execution environment from the runtime environment variable:

`AGPP_ENVIRONMENT`

The value of `AGPP_ENVIRONMENT` must correspond to one of the values defined by the `Environment` enum:

- `development`
- `testing`
- `production`

The runtime value will be resolved into the strongly typed `Environment` enum before application configuration is loaded.

The configuration system will therefore follow this flow:

```text
Runtime environment
        |
        v
AGPP_ENVIRONMENT
        |
        v
Environment resolution
        |
        v
Environment enum
        |
        v
Environment-specific YAML
        |
        v
Validated application configuration