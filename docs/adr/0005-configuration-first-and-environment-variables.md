# ADR-0005: Configuration first and environment variables

- **Status:** Accepted
- **Date:** 2026-10-26
- **Related decisions:** 04 (Configuration first), 05 (Environment variables),
  06 (Business Models), 10 (Exceptions)

## Context

Nothing environment-specific may live in code (Decision 04), and secrets
must never appear in YAML (Decision 05). The platform needs one
predictable way to turn files and environment variables into typed
settings, and it must fail early and safely when they are wrong.

## Decision

1. **Layering.** Configuration is built from `config/base.yaml`, then
   overlaid with `config/<environment>.yaml`. Mappings are merged
   recursively; scalars and lists in the overlay replace the base values.
2. **Environment selection.** `AGPP_ENV` (`development`, `testing`,
   `production`) is required. There is no silent default, so a missing
   value can never fall back to the wrong environment.
3. **Placeholders.** YAML values may reference environment variables as
   `${NAME}` (required) or `${NAME:-default}`. An empty variable counts as
   unset. Placeholders are resolved after merging, so a value that an
   overlay replaces is never resolved.
4. **Secrets** appear in YAML only as placeholders. Real values come from
   the process environment or a local `.env` file (never committed). The
   process environment wins over `.env`. `.env` is read without modifying
   `os.environ`.
5. **Validation.** The resolved data is validated into frozen Pydantic
   models that forbid unknown keys. Passwords use `SecretStr`.
6. **Fail fast and safe.** Invalid configuration raises a
   `ConfigurationError` subclass at startup. Error messages contain field
   names and reasons, never input values.
7. Application code never reads `os.environ`. It receives a validated
   configuration object.

## Alternatives considered

| Option | Why not |
|---|---|
| pydantic-settings only | Handles env vars well but not layered YAML files with placeholders. |
| Environment variables only | Loses reviewable, versioned non-secret settings. |
| Default `AGPP_ENV` to development | A forgotten variable in production would silently run development settings. |

## Consequences

### Positive
- One reviewable place for non-secret settings; secrets stay out of Git.
- Misconfiguration fails at startup with a clear message.
- Typed, immutable settings are easy to test.

### Negative / trade-offs
- A small custom loader to maintain (merge and placeholders).
- Listing and replacing lists wholesale can surprise; this is documented.

### Follow-ups
- implementation of this ADR.
