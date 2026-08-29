# syntax=docker/dockerfile:1.7
# ============================================================================
# Algobattle API — multi-stage Dockerfile
# ============================================================================
# Stages:
#   base     — python + system deps + non-root user
#   deps     — pip install (cached)
#   dev      — dev target with backend mounted for hot reload
#   runtime  — production: gunicorn + uvicorn workers
# ============================================================================

ARG PYTHON_VERSION=3.11

# ----------------------------------------------------------------------------
# Base
# ----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 10001 — high to avoid host collisions)
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app --shell /sbin/nologin app

WORKDIR /app

# ----------------------------------------------------------------------------
# Deps — cached pip layer
# ----------------------------------------------------------------------------
FROM base AS deps

COPY requirements.txt /app/requirements.txt
RUN pip install --prefix=/install -r /app/requirements.txt

# ----------------------------------------------------------------------------
# Runtime
# ----------------------------------------------------------------------------
FROM base AS runtime

COPY --from=deps /install /usr/local
COPY --chown=app:app . /app

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; \
r=urllib.request.urlopen('http://localhost:8000/health', timeout=3); \
sys.exit(0 if r.status==200 else 1)"

# ----------------------------------------------------------------------------
# Dev — same base, but mounts source for hot reload
# ----------------------------------------------------------------------------
FROM base AS dev

COPY --from=deps /install /usr/local

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*

# Override entrypoint for dev (uvicorn --reload is supplied by compose override)
ENTRYPOINT ["/usr/bin/tini", "--", "uvicorn", "app.main:app", \
            "--host", "0.0.0.0", "--port", "8000", "--reload"]
CMD []