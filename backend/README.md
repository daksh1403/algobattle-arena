# Algobattle — backend

TDD-first FastAPI backend for **Algobattle**, a LeetCode-style competitive
coding judge platform.  Built for **cost-effective horizontal scaling**:
the API is stateless (Redis ZSETs back the live leaderboard), and the
heavy work — running user code — is pushed onto an RQ worker pool that
talks to a separate Judge0 instance.

## Stack

| Layer | Tech |
| --- | --- |
| Web | FastAPI 0.115 + uvicorn |
| ORM  | SQLAlchemy 2 (async) + Alembic |
| DB   | PostgreSQL 16 (prod) / SQLite :memory: (tests) |
| Queue / cache | Redis 7 + RQ + ZSETs |
| Judge | Judge0 (self-hosted via Docker, separate service) |
| Auth  | JWT (HS256, 24h) + bcrypt cost 12 |
| Tests | pytest + pytest-asyncio + httpx + fakeredis |

## Project layout

```
backend/
  app/
    main.py                # FastAPI factory + lifespan
    config.py              # pydantic-settings
    db.py                  # async engine + session
    redis_client.py        # async redis client (fakeredis in tests)
    rq_app.py              # RQ queue helper
    deps.py                # FastAPI dependencies (db, redis, current user)
    core/
      security.py          # bcrypt + JWT
      exceptions.py        # custom exceptions + handlers
      pagination.py        # PageParams / Page envelope
    modules/
      users/               # register, login, JWT auth
      problems/            # problems CRUD + LeetCode-style seed data
      contests/            # contests + participants + ContestProblem
      submissions/         # submission lifecycle + Judge0 client + RQ task
      leaderboard/         # Redis ZSET-backed live leaderboard
  tests/
    conftest.py            # fixtures (db_session, client, fake_redis)
    test_integration.py    # end-to-end submit → poll → result
  migrations/
    env.py
    versions/
      0001_initial.py      # schema for every table
  pyproject.toml
  alembic.ini
  Dockerfile
  .env.example
```

## TDD approach

Each module ships its tests in `app/modules/<module>/tests/`:

```
app/modules/users/tests/
  test_service.py      # pure service tests (db_session fixture)
  test_router.py       # httpx-driven router tests (client fixture)
```

Tests are written **first**; the implementation in `service.py` /
`router.py` is the green step.

Run them:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run all tests (uses sqlite-in-memory + fakeredis; no external services required)
pytest -v

# Run a single module
pytest app/modules/users/tests -v
```

## Running locally

```bash
# 1. Start Postgres + Redis + Judge0 (handled by docker compose at the
#    project root — see ../../infra/docker-compose.yml).
cp .env.example .env
alembic upgrade head                 # create tables
python -m app.modules.problems.data.seed   # seed 4 LeetCode-style problems
uvicorn app.main:app --reload        # start the API on :8000

# 2. In another shell — start the RQ worker
rq worker algobattle-judge --url redis://localhost:6379/0
```

## API surface (summary)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register` | – | create account |
| POST | `/auth/login` | – | exchange creds for JWT |
| GET  | `/problems` | – | list problems (filter by `difficulty`, `tag`, `search`) |
| POST | `/problems` | – | create problem (admin) |
| GET  | `/problems/{slug}` | – | fetch one |
| GET  | `/problems/{slug}/testcases` | – | sample test cases |
| GET  | `/contests` | – | list contests |
| POST | `/contests` | – | create contest (admin) |
| GET  | `/contests/{id}` | – | fetch contest |
| POST | `/contests/{id}/join` | JWT | join a running contest |
| GET  | `/contests/{id}/leaderboard` | – | live leaderboard |
| GET  | `/contests/{id}/participants` | – | SQL-derived ranking |
| POST | `/submissions` | JWT | submit code (queued for judging) |
| GET  | `/submissions` | JWT | my submissions |
| GET  | `/submissions/{id}` | JWT | submission + per-testcase results |
| GET  | `/leaderboard/contests/{id}` | – | leaderboard with solve-time tiebreak |

OpenAPI docs: <http://localhost:8000/docs>

## Architecture notes

- **Cost-effective**: API is stateless; only Redis state (ZSETs) is hot.
  Workers are tiny (no DB connection pooling issues — each task creates
  its own short-lived engine).
- **Modular**: each domain lives in its own folder with a single
  `router.py`, `service.py`, `models.py`, `schemas.py`.  Cross-module
  imports go through the module's public `__init__.py`.
- **Production-grade**: tests cover services + routers + integration; the
  judge pipeline is idempotent (re-running a finished submission is a
  no-op); submission status is monotonic.
- **Deterministic**: `submission.status` always advances
  `PENDING → RUNNING → terminal`; the same input + judge yields the same
  verdict (Judge0 is deterministic for a given input).
- **Resilient**: queue-based — judge crashes don't lose submissions, they
  just retry when a worker picks them up again.  A future "stale
  PENDING" sweeper can be added to `tasks.py`.

## Module READMEs

Each module folder has its own README describing the interface contract:

- [`app/modules/users/README.md`](app/modules/users/README.md)
- [`app/modules/problems/README.md`](app/modules/problems/README.md)
- [`app/modules/contests/README.md`](app/modules/contests/README.md)
- [`app/modules/submissions/README.md`](app/modules/submissions/README.md)
- [`app/modules/leaderboard/README.md`](app/modules/leaderboard/README.md)
