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

# Copy the prepared virtual environment, source, built docs, and entrypoint.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/site /app/site
COPY server_run.py ./

ENV PATH="/app/.venv/bin:$PATH"

# Run unprivileged.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Documentation only — the real bind port is read from the PORT env at runtime
# by server_run.py (default 3011). Override the ARG to change what's documented.
ARG PORT=3011
EXPOSE ${PORT}

# server_run.py execs Granian (Rust ASGI server). Scale with the WORKERS env.
CMD ["python", "server_run.py"]
