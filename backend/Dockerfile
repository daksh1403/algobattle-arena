# syntax=docker/dockerfile:1.7
# =============================================================================
# Algobattle backend — multi-stage Dockerfile
#
# Stage 1 (builder):  installs build deps + app deps into a virtualenv
# Stage 2 (runtime):  minimal image with only the runtime virtualenv
# =============================================================================

# ---------- builder ---------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# Install uv (fast installer) — falls back to pip if you prefer.
RUN pip install --upgrade pip wheel

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml ./

# Use pip to install everything (no need for full poetry export pipeline)
RUN pip wheel --wheel-dir=/wheels \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "email-validator>=2.1.0" \
    "SQLAlchemy[asyncio]>=2.0.30" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0" \
    "redis>=5.0.0" \
    "rq>=1.16.0" \
    "python-jose[cryptography]>=3.3.0" \
    "passlib[bcrypt]>=1.7.4" \
    "bcrypt>=4.0.0,<4.1" \
    "httpx>=0.27.0" \
    "python-multipart>=0.0.9" \
    "python-dotenv>=1.0.0"

# ---------- runtime ---------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /bin/bash algobattle

WORKDIR /app

# Install wheels from builder (single clean pass — the fallback line was a typo)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
    fastapi "uvicorn[standard]" pydantic pydantic-settings email-validator \
    "SQLAlchemy[asyncio]" asyncpg alembic redis rq \
    "python-jose[cryptography]" "passlib[bcrypt]" bcrypt httpx \
    python-multipart python-dotenv \
 && rm -rf /wheels

# Copy source code
COPY . /app

USER algobattle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]

# Default to the API server.  Use `docker run <image> worker` to start the
# RQ judge worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
