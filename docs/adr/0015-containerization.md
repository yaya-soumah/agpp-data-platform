# ADR-0015: Containerization

- **Status:** Accepted
- **Date:** 2026-11-06
- **Related decisions:** 04 (Configuration first), 05 (Environment variables),
  08 (Orchestration)

## Context

The pipeline must run the same way on a laptop, in CI and later under an
orchestrator. It needs a reproducible image that contains no secrets and no
development tooling.

## Decision

1. **Multi-stage image.** A builder stage installs the locked, non-development
   dependencies and the package with `uv`; the runtime stage copies only the
   virtual environment, `config/` and `sql/`.
2. **Locked dependencies.** The build uses `uv sync --locked`, so the image
   contains exactly what `uv.lock` says.
3. **No secrets, no development files.** `.dockerignore` excludes `.env`,
   `tests/`, caches and local data. Credentials arrive as environment
   variables at run time (ADR-0005).
4. **Non-root.** The process runs as an unprivileged user (uid 10001).
5. **Defaults.** `AGPP_ENV=production` (JSON logs to stderr, no log file). The
   entry point is the `agpp` command, so the image is used as
   `docker run <image> run-supplier-product`.
6. **Data is a volume.** Input files live outside the image and are mounted at
   `/app/data`.
7. **Compose.** The `app` service sits behind a Compose profile, so
   `docker compose up -d` still starts only PostgreSQL. It reaches the
   database by its service name.
8. **CI.** CI builds the image on every pull request and checks that it starts,
   runs as non-root and contains neither `.env` nor tests. The image is not
   published yet because there is no registry in scope.

## Consequences

### Positive
- The same artifact runs locally, in CI and later in an orchestrator.
- Small attack surface and no secrets in layers.

### Negative / trade-offs
- `uv` is installed with `pip` in the builder stage, so its version is not
  pinned yet; the lock file still fixes every dependency.
- Bind-mounted data folders can have permission problems on Linux hosts when
  the host user is not uid 10001.

### Follow-ups
- Publish the image to a registry from CI on tagged releases.
- Run the pipeline from Airflow using this image.
