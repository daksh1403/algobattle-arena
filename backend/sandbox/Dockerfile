# AlgoBattle Judge — production image
# Runs the FastAPI web_arena on port 8080 with Python/C++/Java compilers
# and a non-root sandbox user. Designed for a VPS behind a cloudflared
# named tunnel.
#
# Build:
#   cd backend
#   docker build -t algobattle-judge -f sandbox/Dockerfile .
# Run:
#   docker run -d --restart=always --name algobattle-judge \
#     -p 8080:8080 \
#     -v algobattle-data:/data \
#     algobattle-judge

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

# Compilers + runtimes for the three supported languages, plus Python deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        g++ \
        openjdk-17-jdk-headless \
        curl \
        ca-certificates \
        locales \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Non-root sandbox user (the judge runs code as this user inside the container)
RUN useradd -m -s /bin/bash sandbox \
    && mkdir -p /data \
    && chown -R sandbox:sandbox /data

WORKDIR /app

# Install Python deps first (layer caching)
COPY sandbox/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Judge source
COPY sandbox/__init__.py /app/sandbox/__init__.py
COPY sandbox/sandbox_runner.py /app/sandbox/sandbox_runner.py
COPY sandbox/web_arena.py /app/web_arena.py

# Healthcheck: verify the API is up and the sandbox can run code
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

USER sandbox
EXPOSE 8080

# Persistent leaderboard file lives in /data (mount a volume here)
ENV ARENA_DATA_FILE=/data/arena_data.json

CMD ["python3", "-m", "uvicorn", "web_arena:app", "--host", "0.0.0.0", "--port", "8080"]
