# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN pip install --no-cache-dir "uv>=0.5"

WORKDIR /app

# Dependencies first, so this layer is cached until the lock file changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-editable --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --no-editable


FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 agpp

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY config ./config
COPY sql ./sql

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AGPP_ENV=production

USER agpp

ENTRYPOINT ["agpp"]
CMD ["--help"]
