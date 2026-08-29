# syntax=docker/dockerfile:1.7
# ============================================================================
# Algobattle Judge Worker — Dockerfile
# ============================================================================
# Runs RQ worker. Polls Redis, submits code to Judge0, posts results back.
# ----------------------------------------------------------------------------

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/prom_multiproc \
    && groupadd --system --gid 10002 worker \
    && useradd --system --uid 10002 --gid worker --home /app --shell /sbin/nologin worker

WORKDIR /app

FROM base AS deps

COPY requirements.txt /app/requirements.txt
RUN pip install --prefix=/install -r /app/requirements.txt

FROM base AS runtime

COPY --from=deps /install /usr/local
COPY --chown=worker:worker . /app

# Prometheus multiproc dir must be writable by the user
RUN mkdir -p /tmp/prom_multiproc && chown -R worker:worker /tmp/prom_multiproc

USER worker

EXPOSE 9100

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["rq", "worker", "--url", "${REDIS_URL}", "--name", "judge-worker", \
     "--burst", "--with-scheduler", "${RQ_QUEUE_NAME:-submissions}"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,redis,sys; \
r=redis.Redis.from_url(os.environ['REDIS_URL']); \
ks=r.keys('rq:worker:*'); sys.exit(0 if any(b'judge-worker' in k for k in ks) else 1)"

FROM base AS dev

COPY --from=deps /install /usr/local
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/bin/tini", "--", "rq", "worker", "--url", "${REDIS_URL}"]
CMD ["${RQ_QUEUE_NAME:-submissions}"]