# ADR-004: Environment Variable Strategy

- **Status:** Accepted
- **Date:** 2026-08-04
- **Deciders:** AGPP Engineering Team

## Context

The AGPP Data Platform requires access to sensitive information in order to interact with external systems, including databases, cloud services, third-party APIs, and authentication providers.

Examples of sensitive information include:

- Database usernames and passwords
- API keys
- Access tokens
- Encryption keys
- Cloud service credentials

Unlike general application configuration, these values are confidential and must not be exposed through source control, documentation, log files, or deployment artifacts.

At the same time, developers, automated testing environments, and production deployments must each be able to provide their own credentials without requiring changes to the application source code.

The platform therefore requires a secure, standardized, and environment-independent strategy for managing secrets.

## Decision

The AGPP Data Platform separates **configuration** from **secrets**.

Application configuration describes how the platform behaves and is stored in version-controlled configuration files (see ADR-003).

Sensitive information is supplied through environment variables at runtime and is never stored in the repository.

The platform follows these principles:

- Secrets must never be committed to version control.
- Secrets must never appear in YAML configuration files.
- Secrets must never be hardcoded in source code.
- Secrets must never be written to log files or error messages.
- All environments provide their own environment variables independently.
- The application reads secrets during startup through a centralized configuration component.
- A `.env_example` file documents the required environment variables without containing real values.
- The local `.env` file is intended only for development and must be excluded from version control.

The repository includes:

```text
.env
.env_example
```

where:

- `.env` contains developer-specific secret values and is ignored by Git.
- `.env_example` serves as documentation for required variables and contains placeholder values only.

This strategy ensures that application code remains portable while credentials remain external to the repository.

## Consequences

### Positive

- Prevents accidental exposure of sensitive credentials.
- Supports secure deployments across development, testing, and production environments.
- Aligns with industry best practices and the Twelve-Factor App methodology.
- Enables each environment to manage credentials independently.
- Simplifies credential rotation without requiring code changes.
- Keeps the repository safe to share publicly.

### Negative

- Application startup depends on the presence of correctly configured environment variables.
- Missing or invalid environment variables can prevent the application from starting.
- Deployment environments require additional operational configuration to supply secrets.

### Neutral

- The mechanism used to provide environment variables is deployment-specific and may vary between local development, CI/CD pipelines, containers, or cloud platforms.
- Secret management systems may evolve over time without changing this architectural decision.
- Future integrations with dedicated secret management services remain compatible with this strategy.
