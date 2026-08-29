# Algobattle — Architecture

## High-level

```
                                     ┌─────────────────────────────────┐
                                     │      VS Code Extension          │
                                     │  (algobattle.login / .runTests) │
                                     └─────────────┬───────────────────┘
                                                   │ HTTPS / JWT
                                                   ▼
┌──────────────────┐      ┌────────────────────────────────────────────┐
│  React Frontend  │◀────▶│             FastAPI Backend                 │
│  + Monaco Editor │ HTTPS│  • /auth  • /problems  • /contests         │
└──────────────────┘      │  • /submissions  • /leaderboard            │
       │                  │  • WebSocket /ws                            │
       │ WS                └─────┬────────────────────┬─────────────────┘
       │                        │ RQ enqueue           │ read/write
       ▼                        ▼                      ▼
┌────────────────────┐  ┌────────────────────┐  ┌──────────────┐
│   Traefik          │  │ Redis 7            │  │ PostgreSQL 16│
│   (HTTPS / LE)     │  │ • Sorted Sets leaderboard                  │
│                    │  │ • List: judge queue                       │
│                    │  │ • Pub/Sub: live updates                   │
└────────────────────┘  └────────┬───────────┘  └──────────────┘
                                │ RQ worker
                                ▼
                        ┌──────────────────────┐
                        │  Judge Worker (Python)│
                        │  ─ orchestrates ────▶│
                        │  Judge0 (Docker, isolate)
                        │   • CPU/cgroup limits │
                        │   • No network       │
                        │   • Per-job tmpfs    │
                        └──────────────────────┘
                                  │
                                  ▼
                       Prometheus + Grafana
                       (logs → Loki, metrics → Prom)
```

## Data Flow — A Submission End-To-End

1. User writes code in Monaco (web) or VS Code extension.
2. User clicks **Test** → `POST /api/submissions/run` with `{problem_id, language, code}`.
3. API persists `Submission(status=PENDING)` row, enqueues `{"submission_id", "mode":"test"}` to Redis list `algobattle:queue:judge`.
4. API returns `202 Accepted` with `{submission_id, status_url: "/submissions/{id}"}`.
5. Frontend polls OR subscribes via WebSocket to `/ws/submissions/{id}`.
6. **Judge Worker** picks up the job:
   - Fetches submission + problem + visible-testcases (test mode) or all-testcases (submit mode).
   - POSTs batch to Judge0 `/submissions/batch?base64_encoded=true&wait=false` with one sub-submission per testcase.
   - Polls Judge0 `/submissions/{token}/batch` until all done.
   - Maps Judge0 statuses to our `VERDICT` enum.
   - Writes `SubmissionResult` rows (one per testcase).
   - Sets `Submission.status` (first-failure-wins for submit mode; per-testcase for test mode).
   - If contest + verdict=ACCEPTED → `ZINCRBY algobattle:contest:{id}:leaderboard score user_id`.
   - Publishes verdict via Redis pubsub topic `algobattle:pubsub:submission:{id}`.
   - API WebSocket gateway subscribes and pushes to client.

## Key Design Decisions

### Why Judge0 (not custom sandbox)?

Judge0 is the de-facto open-source code execution system (4.4k stars, used by academia + commercial platforms). It uses IOI's `isolate` for sandboxing (the same code that powers the international olympiads). Building this from scratch would be ~2 weeks of Linux kernel work. **We use it as a black box** and add our orchestration layer (verdict aggregation, leaderboard updates, periodic checker).

### Why RQ (not Celery)?

RQ is simpler, has lower ops overhead, and is sufficient for ≤1000 submissions/min. For higher scale (>1000/min), Celery's prefetch/queue/routing might be necessary, but that's a V2 concern.

### Why FastAPI (not Django)?

- Native async = no thread pool overhead under contest load
- Native WebSocket (Django Channels requires additional infra)
- Pydantic v2 schemas double as validators + openapi
- Smaller boilerplate per endpoint

### Why feature-first in frontend?

Each feature folder is self-contained — `features/auth` has its own page, hook, service. This prevents the typical React app from collapsing into `components/Megalodon.tsx`.

### Why SecretStorage (not localStorage) in VS Code?

LocalStorage can be exfiltrated by any other extension with a similar URI scheme. SecretStorage uses OS-level keystore (macOS Keychain, Windows DPAPI, Linux libsecret). Same pattern by GitHub Copilot, official extensions.

## Modules (backend)

| Module | Responsibility |
|---|---|
| `users` | register, login, JWT issuance, password hashing |
| `problems` | CRUD, list with filter, problem + testcases |
| `contests` | contest lifecycle, participant registration |
| `submissions` | submit/run, enqueue, status tracking |
| `leaderboard` | Redis ZSET ops, score keeping, rank computation |

Each module follows the same shape:

```
app/modules/<name>/
├── __init__.py
├── models.py     # SQLAlchemy
├── schemas.py    # Pydantic
├── service.py    # business logic
├── router.py     # FastAPI APIRouter
└── tests/
    ├── __init__.py
    ├── test_service.py
    └── test_router.py
```

Cross-module dependencies are explicit: `submissions/service.py` imports `problems.service` and `leaderboard.service` — never the other way. This keeps the dependency graph DAG-shaped.

## Concurrency Model

- **API**: async ASGI workers (gunicorn -k uvicorn.workers.UvicornWorker -w 2) — 2 worker processes, each with its own event loop. Tune `-w` based on CPU cores.
- **Judge worker**: RQ worker with `--concurrency 4` — 4 jobs per worker process. Run multiple worker processes for higher throughput.
- **Leaderboard updates**: atomic `ZINCRBY` (server-side, no race).
- **WebSocket connections**: one per client, multiplexed by topic.

## Failure Modes & Mitigations

| Failure | Detection | Recovery |
|---|---|---|
| Worker crashes mid-judging | Submission stuck in RUNNING >60s | Periodic checker re-enqueues |
| Judge0 transient error | HTTP 5xx or non-terminal status | Retry 3x with backoff |
| Judge0 hard down | All submissions → JUDGE_ERROR | Notified via Prometheus alert |
| Postgres down | Connection errors | API returns 503, queue keeps jobs |
| Redis down | API degraded (no queue, no live leaderboard) | Submissions stay 503 until recovery |
| Worker / host dies | Submissions stuck | Checker on a different host re-enqueues |
| Two workers grab the same job | RQ's atomic `BLPOP` prevents | RQ semantics |
| User submits the same code many times | All create independent submissions | Allowed (per problem per contest); rate-limit per IP |
| Infinite loop | Judge0 wall-clock timer | TLE verdict |
| Memory bomb | cgroup memory.max → OOM kill | MLE verdict |
| Disk filling up | — | docker volume size limit + lvm on host |
| Network access during judging | `isolate` drops NET namespace | Network I/O errors → RUNTIME_ERROR |
| Filesystem escape | tmpfs + read-only fs | symlink → noescape (CVE-2024-28185) — we pin Judge0 ≥ 1.13.2 |

## Observability

Every service exposes Prometheus `/metrics`:

- **API**: request count, latency histograms, error rate, WebSocket connections gauge
- **Worker**: queue depth gauge, jobs processed counter, retry counter, judge latency histogram
- **Judge0**: built-in Prometheus exporter (submissions processed, timeouts, languages breakdown)
- **Postgres** via `postgres_exporter`: connection count, qps, slow queries, replication lag
- **Redis** via `redis_exporter`: memory, ops/sec, connection count
- **Node** via `node_exporter`: CPU, memory, disk, network

Grafana dashboards pre-loaded: judge-performance, api-health, leaderboard-liveness.

Alerts:
- `judge_queue_depth > 1000 for 15m` — workers can't keep up; spin up more
- `judge_error_rate > 5% for 5m` — Judge0 problem or code bug
- `api_p99_latency > 2s for 5m` — API overloaded
- `judge0_down for 1m` — page on-call
- `postgres_disk > 80%` — provision more

## Security

- All secrets in env (mounted via Docker secrets in prod), never committed
- JWT secret rotated via `rotating-secret` (env var refreshed on every container restart)
- Judge0 has no network access
- Rate limiting: 60 req/min/IP via Traefik middleware
- CORS: only frontend origin allowed
- CSP, X-Frame-Options, HSTS via Traefik headers middleware
- VS Code extension: JWT in SecretStorage, not localStorage
- Helm chart: Judge0 runs with `seccomp: RuntimeDefault`, `runAsNonRoot: true` (note: cgroups need privileged — handle via dedicated nodeSelector + toleration)

## Cost Optimization Summary

- Scale to zero: EC2 Spot for judge worker (60–70% cheaper) — can be interrupted without losing submissions because of queue-based design.
- Single-AZ deployment to avoid HA costs in dev/staging.
- CloudWatch alarms instead of full observability stack in staging.
- Self-host Judge0 instead of paying Sphere Engine ($0.30/submission vs $0 fixed infra).
- Use SQLite for the queue debug mode (defer to V2; we don't ship this in V1).

## Decision Log

| Decision | Alternatives considered | Chosen |
|---|---|---|
| Judge engine | Custom sandbox / Sphere Engine / Judge0 | Judge0 — battle-tested, free, no vendor lock |
| Queue | RQ / Celery / SQS / Kafka | RQ — small ops surface, sufficient scale |
| Frontend build | Next.js / CRA / Vite | Vite — fast HMR, small bundle, modern |
| Editor in browser | CodeMirror / Monaco / Ace | Monaco — same engine as VS Code, full feature parity |
| Auth | JWT-only / Sessions / OAuth | JWT — stateless, simple, works for WebSocket |
| DB | Postgres / MySQL | Postgres — better array types for tags, JSONB for test cases |
| Live updates | SSE / WebSocket / polling | WebSocket — supports bidirectional, lower latency |
| Repo layout | monorepo / polyrepo | monorepo — easier local dev, single CI |
| Cloud | AWS / GCP / Azure / self-host | AWS — best free tier + spot pricing |
