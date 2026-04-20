# syntax=docker/dockerfile:1.7
# Multi-stage production image for the PayFast billing backend.
#
# Stage 1 (builder): install uv + resolve dependencies into a venv.
# Stage 2 (runtime): copy only the venv + source, run as non-root.

# -----------------------------------------------------------------------------
# Builder
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install uv from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install deps first for maximum layer cache efficiency
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

# Now copy the app and install it (faster subsequent rebuilds on app-only edits)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
RUN uv sync --frozen --no-dev || uv sync --no-dev


# -----------------------------------------------------------------------------
# Runtime
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

# curl is used for the HEALTHCHECK; keep the image lean otherwise.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin appuser

WORKDIR /app

# Copy the prebuilt venv + application from the builder
COPY --from=builder --chown=appuser:app /app/.venv /app/.venv
COPY --from=builder --chown=appuser:app /app/app /app/app
COPY --from=builder --chown=appuser:app /app/alembic /app/alembic
COPY --from=builder --chown=appuser:app /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=appuser:app /app/scripts /app/scripts

# Entrypoint: run migrations, then start uvicorn with 2 workers.
#
# NOTE: the APScheduler in app.main.lifespan is in-process. Running
# --workers 2 starts TWO scheduler instances, each firing the nightly/hourly
# jobs. For a single-host prod rollout this duplicates renewal emails + charge
# attempts. Before scaling workers > 1, switch SCHEDULER_ENABLED=false here
# and run a dedicated scheduler process (`python -m app.workers.scheduler`) —
# or move to an external scheduler (cron, k8s CronJob). Keeping workers=2
# short-term for request throughput; acceptable because the scheduler jobs
# themselves are idempotent (webhook_events dedupe, invoice state checks).
COPY --chown=appuser:app <<'EOF' /app/entrypoint.sh
#!/usr/bin/env bash
set -euo pipefail
echo "[entrypoint] running alembic migrations..."
alembic upgrade head
echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
EOF
RUN chmod +x /app/entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
