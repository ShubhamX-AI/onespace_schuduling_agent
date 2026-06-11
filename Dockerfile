# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Install the project.
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Build the documentation site (served by the app at /documentation).
COPY mkdocs.yml ./
COPY docs ./docs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv run --group docs mkdocs build --strict


FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Copy the prepared virtual environment, source, and built docs.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/site /app/site

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
# Granian (Rust ASGI server) for high-throughput I/O. Scale with --workers.
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "app.main:app"]
