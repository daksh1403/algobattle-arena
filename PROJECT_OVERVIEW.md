# AlgoBattle — Complete Project Overview

> Everything the project does, how it works end-to-end, every problem we
> hit, how we fixed it, and how the tricky parts (auth, edge cases, access
> control, sandboxing, persistence) are handled. Single source of truth for
> the GDG walkthrough, a new contributor onboarding, or a future-you in 6
> months who forgot everything.

---

## 1. What AlgoBattle is

A competitive coding platform in the style of LeetCode / Codeforces, built
for the GDG VIT Chennai speed-coding event. Participants:

1. Pick a problem
2. Write code (Python, C++, or Java) in an in-browser editor
3. Hit **Run** to test against visible sample cases
4. Hit **Submit** to test against the full hidden test suite
5. Get a verdict (`AC` / `WA` / `TLE` / `MLE` / `RE` / `OLE` / `CE`) and a
   score on a live leaderboard

The project lives in two layers: a **deployed** in-house Python sandbox +
Cloudflare edge (what's actually live at `https://algobattle-arena.dakshx.workers.dev/`),
and a **more elaborate** FastAPI + Postgres + Redis + RQ + Judge0 backend
in `backend/app/` (heavier, more features, not currently the live path).

---

## 1a. Architecture diagrams

| Diagram | What it shows |
|---|---|
| [`docs/architecture_deployed.svg`](docs/architecture_deployed.svg) | The **live** path: Browser → Cloudflare Worker → KV (always-on edge) + Cloudflare Tunnel → local judge (`web_arena.py`) |
| [`docs/architecture_scalable.svg`](docs/architecture_scalable.svg) | The **production-scalable** path: Browser → FastAPI → Postgres + Redis, RQ workers → Judge0 sandbox, WebSocket live updates |

---

## 1b. Which architecture is the project? (read this first)

There are **two legitimate architectures in this repo**. They are not
competing — they are two deployment stages of the same product:

| | **Path A — Live demo** | **Path B — Production-scalable** |
|---|---|---|
| **Where** | `backend/sandbox/web_arena.py` | `backend/app/` (FastAPI) |
| **What it is** | Single-host judge: FastAPI + subprocess sandbox, exposed via Cloudflare Tunnel | Distributed judge: FastAPI + Postgres + Redis + RQ worker pool + Judge0 sandbox |
| **Deployed?** | ✅ Yes, live at `algobattle-arena.dakshx.workers.dev` | ❌ Code complete, ready to deploy |
| **Sandbox** | In-house `SandboxRunner` (RLIMIT_AS/CPU/FSIZE + wall-clock kill) | Judge0 + IOI `isolate` (cgroups, kernel-level isolation) |
| **Persistence** | Cloudflare KV (leaderboard) + in-memory contests | PostgreSQL (source of truth) + Redis ZSETs (live leaderboard) |
| **Scale** | 1 host, 1 process. Fine for a class / hackathon | Horizontal: add RQ workers, more API instances. Fine for production |
| **Why it exists** | Zero-cost, 2-minute deploy, demo-friendly | The "real" system — what you'd run for thousands of users |

**If you are a judge / reviewer:** start at **Path B** (`backend/app/`) to
see the production-grade architecture — async SQLAlchemy, JWT auth with
bcrypt cost 12, idempotent state machine, stuck-submission sweeper,
rate limiting, Redis-backed leaderboard. Then look at **Path A**
(`backend/sandbox/`) to see the live, zero-cost deployment. Both share
the same Cloudflare edge and the same Worker proxy; swapping the judge
backend is a one-line `TUNNEL_URL` change.

---

## 2. The deployed architecture (the one that's actually live)

```
Browser
   │
   ▼
Cloudflare Worker  →  algobattle-arena.dakshx.workers.dev
   │
   ├── [assets]  static frontend (single index.html, ~2k lines, no framework)
   ├── [KV]      /api/leaderboard, /api/submissions, /health  (always online)
   │
   └── /api/submit, /api/compiler/run, /api/problems/*, /standings/stream
        │
        ▼  (HTTPS, via TUNNEL_URL secret)
        │
   Cloudflare Tunnel  →  *.trycloudflare.com
        │
        ▼  (localhost, only)
        │
   Local judge  →  web_arena.py on :8080 (FastAPI + sandbox)
```

**Why this shape:** Cloudflare Workers run at the edge and **cannot execute
subprocesses** (no Python, no g++, no JVM). So the judge runs where it
*can* — on a real box with a real OS — and the Worker securely proxies
requests to it through a tunnel. Frontend is 100% static on Cloudflare's
CDN, leaderboard persists in Workers KV. When the judge is offline the
Worker returns a graceful 502 with a clear message instead of a broken
page.

**Persistence split:**
- **Cloudflare KV** — submissions + leaderboard (cloud-persistent, always
  readable, survives judge restarts)
- **Local file** (`arena_data.json` in `/data` volume in the Docker
  image) — contests + participants + per-user stats. Resets when the
  judge container is recreated unless a volume is mounted.

---

## 3. The non-deployed backend architecture (`backend/app/`)

A heavier system that exists in the repo but is **not** what the live site
uses. Kept around because it's more feature-complete and is the natural
migration target.

```
Browser
   ▼
FastAPI (uvicorn)  ──  /api/*  ──┐
   │                              │
   ├── Postgres  ◀── users, problems, contests, submissions
   ├── Redis     ◀── queue + ZSET leaderboard
   │
   └── enqueue  ──▶  RQ worker (rq worker)
                          │
                          ▼
                       Judge0 (Docker, IOI isolate)
                          │
                          ▼
                       per-testcase verdict
                          │
                          ▼
                       callback to API
                          │
                          ▼
                       publish to Redis pubsub
                          │
                          ▼
                       WebSocket → browser live update
```

| Piece | Why |
|---|---|
| **FastAPI** | Async-native, Pydantic-validated, OpenAPI for free |
| **Postgres** | Source of truth for everything durable |
| **Redis** | RQ queue + leaderboard ZSETs + WebSocket pubsub + cache |
| **RQ worker** | Stateless judge runner; multiple workers = scale-out |
| **Judge0** | Industry-standard code-execution sandbox, runs user code in cgroups/isolate |
| **WebSocket** | Live status push (PENDING → RUNNING → terminal) without polling |
| **APScheduler** | Periodic stuck-submission sweeper every 60 s |
| **slowapi** | Rate limiting (30/min on `/submissions`) |

The two architectures can coexist: the Worker can be repointed to the
FastAPI backend by changing `TUNNEL_URL`. The Worker code already supports
both `/api/leaderboard` (KV fallback) and generic proxy paths.

---

## 4. Request lifecycle — submission end-to-end (live deployed path)

1. **User clicks Submit** in the browser
2. **Worker receives `POST /api/submit`** at `algobattle-arena.dakshx.workers.dev`
3. **Worker forwards** the request body via the tunnel to `web_arena.py`
4. **`web_arena.py`** stores the submission in memory and the Worker also
   pushes a record into **Cloudflare KV** for persistence
5. **`web_arena.py` runs the code** in the `SandboxRunner`:
   - For Python: writes to a temp file, `subprocess.Popen([python3, -u, tmp], ...)`
   - For C++: `g++ -O2` to compile, then exec the binary
   - For Java: `javac` + `java -Xmx256m ...` (with the JVM-trick from A1-10)
   - Sets `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_FSIZE` in `preexec_fn` to
     cap memory, CPU, and output size
   - Watches with a wall-clock timer that SIGKILLs the process group
   - Polls `proc.wait()` for return code; maps exit code → verdict
6. **Result is appended to KV** with the participant name, problem,
   language, verdict, score, efficiency
7. **Leaderboard** is recomputed from KV (sorts by score desc, then
   efficiency asc)

**Latency:** a single Python submission typically completes in 1-2 s end-to-end.
Compiled languages: ~2 s for C++ (compile + run) and ~3-4 s for Java (JVM warmup).

---

## 5. Request lifecycle — submission end-to-end (FastAPI backend, if deployed)

1. **User clicks Submit** → `POST /api/submissions` (FastAPI)
2. **Pydantic validates** the payload (`SubmissionCreate` schema: problem_id,
   language, code, mode, optional contest_id)
3. **JWT auth** via `get_current_user_id` dep — extracts `sub` from the
   HS256 token, returns `int(user_id)` or raises 401
4. **Rate limit check** via slowapi (`30/min` per IP)
5. **Service layer** (`SubmissionService.submit`):
   - Validates the problem exists
   - Creates a `Submission` row with `status=PENDING`
   - Enqueues an RQ job (or awaits inline in tests)
6. **Response 201** with the submission row (caller polls for verdict)
7. **RQ worker** picks up the job, runs `judge_submission(submission_id)`:
   - Marks the submission `RUNNING`
   - Loads problem + testcases (sample-only for `mode='test'`, all for
     `mode='submit'`)
   - Builds Judge0 batch payloads
   - Sends to Judge0, polls until terminal
   - On HTTP error, **does not** silently fall back to local sandbox in
     production (see §11-E1-3 below)
   - Persists per-testcase `SubmissionResult` rows
   - Updates `Submission.status` to terminal + `runtime_ms` + `memory_kb`
   - If AC and part of a contest: updates `ContestParticipant.total_points`
     and the Redis ZSET leaderboard
   - Publishes status changes to Redis pubsub
8. **WebSocket router** (`ws_router`) receives the pubsub event and
   pushes to connected browsers
9. **Browser** updates the UI live without polling

---

## 6. Authentication and access control

### 6.1 User registration & login

```
POST /api/auth/register
  body: {username, email, password}
  - Pydantic: username 3-32 chars [a-zA-Z0-9_.-], email RFC-valid, password 8-128 chars
  - bcrypt cost 12 hash of the password
  - returns 201 with UserOut (including is_admin=false) and TokenOut with JWT

POST /api/auth/login
  body: {username_or_email, password}
  - single SELECT by username OR email
  - bcrypt verify (constant-time)
  - returns 200 with JWT (HS256, 24h expiry, sub=user_id)
```

**Why HS256 and not RS256:** single-service deployment, no need for
asymmetric verification. Switching to RS256 is one config change.

**Why a 24h JWT:** balances UX (don't make people log in every hour) with
blast radius (a stolen token is good for one day). Production should also
add refresh tokens + a token-revocation list — currently not implemented.

### 6.2 Authorization model

| Endpoint | Auth | Authorization |
|----------|------|---------------|
| `POST /api/auth/register` | none | open (gated by `FEATURE_REGISTRATION_OPEN` env) |
| `POST /api/auth/login` | none | open |
| `GET /api/problems` | none | public read |
| `POST /api/problems` | JWT | **admin only** (any user → 403) |
| `GET /api/contests` | none | public read |
| `POST /api/contests` | JWT | **admin only** |
| `POST /api/contests/{id}/join` | JWT | open to any logged-in user, only during contest window |
| `POST /api/submissions` | JWT | logged-in user, 30/min rate limit |
| `GET /api/submissions` | JWT | **own submissions only** |
| `GET /api/submissions/{id}` | JWT | **own only** (404 on others — see E1-1) |
| `GET /api/leaderboard/contests/{id}` | none | public read |

**Admin elevation** is **only** possible via direct DB write — there is
no admin-promotion endpoint. This is intentional: prevents privilege
escalation via API.

### 6.3 The CORS configuration

`allow_origins=["*"]` with `allow_credentials=True` — **misconfigured**.
Starlette silently rejects credentialed cross-origin requests when origin
is `*`, so the browser will block authenticated requests from a different
domain. Fix needed (E2-2): replace with the specific frontend origin in
production.

### 6.4 Production JWT secret

`config.py` ships with `jwt_secret = "dev-secret-change-me"`. A
`@model_validator(mode="after")` now refuses to start in production with
the default (E1-4) — fails fast with a clear error instead of silently
accepting a publicly-known signing key.

---

## 7. Edge case handling

### 7.1 Submission status state machine

```
PENDING ──▶ RUNNING ──▶ ACCEPTED
                     ├──▶ WRONG_ANSWER
                     ├──▶ TIME_LIMIT_EXCEEDED
                     ├──▶ MEMORY_LIMIT_EXCEEDED
                     ├──▶ RUNTIME_ERROR
                     ├──▶ COMPILE_ERROR
                     └──▶ INTERNAL_ERROR
```

**Invariant:** `PENDING → RUNNING → terminal` (no transitions out of
terminal). Enforced in `judge_submission`:
- `if submission.status in TERMINAL_STATUSES: return` (idempotency)
- `submission.status = RUNNING` before any test runs

**Edge case:** if the worker crashes mid-grading, the submission is left
in `RUNNING` forever. The **stuck-submission sweeper** (APScheduler,
every 60 s) re-enqueues anything non-terminal older than 60 s. Re-enqueue
is safe because the worker rechecks `status in TERMINAL_STATUSES` on
pickup.

### 7.2 Sandbox edge cases (the ones that bit us)

| Disruption | How the sandbox handles it |
|---|---|
| **Infinite loop** (`while True: pass`) | Wall-clock timer fires after `time_limit_s + 0.5`, SIGKILLs the process group. Exit code `-1` → `TLE`. |
| **Infinite recursion** (`def f(): return f()`) | Python `RecursionError` raised → non-zero exit → `RE`. |
| **Memory bomb** (`while True: lst.append(x)`) | `RLIMIT_AS` pre-exec caps virtual address space. On macOS `RLIMIT_AS` cannot be lowered (kernel limit), so memory bombs TLE via the wall-clock kill instead of getting a proper MLE. |
| **Output flood** (`print("x"*1_000_000)`) | `RLIMIT_FSIZE` → `SIGXFSZ` → `OLE`. On macOS, SIGXFSZ requires stdout be redirected to a real file (not a pipe), so the runner does that explicitly. |
| **Division by zero** | `ZeroDivisionError` → non-zero exit → `RE`. |
| **Index error, type error, key error, attribute error** | All raise Python exceptions → non-zero exit → `RE`. |
| **JVM in container** | `RLIMIT_AS` is set to 2 GB, but the JVM heap is capped with `-Xmx256m -XX:MaxMetaspaceSize=128m -XX:ReservedCodeCacheSize=64m`. Real RSS stays at ~35 MB; without this trick, the JVM refuses to start with "Could not reserve enough space for 262144KB object heap" in containers with tight memory limits. |
| **Compile-time TLE** (8 parallel C++ compiles exceed 3 s) | Compiled languages get 10 s wall budget; Python gets 3 s. |

### 7.3 Concurrency and race conditions

**Problem:** two workers could pick up the same submission if RQ's
de-duplication failed. **Solution:** the worker rechecks
`status in TERMINAL_STATUSES` at the top of `judge_submission`. Even if
two workers race, the second one sees the terminal status and bails.

**Problem:** AC + contest scoring — if two AC submissions for the same
problem complete simultaneously, both could try to grant points. **Solution:**
`adjust_points` is conditional — only grants if `already_accepted` is
False (checked with a separate query). The ZSET leaderboard uses
`ZADD NX` semantics for `add_participant` (idempotent init).

**Problem:** the SQL + Redis ZSET can diverge if a worker dies between
the SQL commit and the ZSET update. **Current state:** no reconciliation
sweeper. The ZSET is the live leaderboard, the SQL is the source of truth
— they would need a periodic "rebuild ZSET from SQL" job to recover.
**Not implemented** — open issue (E2).

### 7.4 Input validation edge cases

- **Empty code submission** → Pydantic `min_length=1` rejects
- **100 KB+ code submission** → Pydantic `max_length=100_000` rejects
- **Unknown language** → defaults to Python (Judge0 id 71) — silent
  default, could be a logged warning
- **Unknown problem_id** → `NotFoundError` 404
- **Contest submission outside window** → **currently NOT blocked** (E2-1)
- **Submission to a contest the user didn't join** → **currently NOT blocked** (E2-1)

### 7.5 Output truncation

Per-testcase stdout/stderr/compile_output is truncated to **8000 chars**
before persisting. A user with verbose output gets truncated results
silently — no warning surfaced in the UI. Minor UX issue.

### 7.6 Duplicate registration

`username` and `email` both have unique constraints at the DB level and
a pre-check at the service level (`or_(username == X, email == X)`).
Duplicate → 409 `ConflictError`. The error message is intentionally
generic ("username or email already exists") to avoid leaking whether
*which one* is taken.

---

## 8. Persistence model

### 8.1 Live deployment (KV + file)

| Data | Where | Survives judge restart? |
|---|---|---|
| Submission history (per submission: id, participant, problem, language, verdict, score, efficiency, runtime, created_at) | Cloudflare KV `arena:submissions` | ✅ |
| Leaderboard (derived from submissions) | Recomputed on each request from KV | ✅ |
| Contests + participants | In-memory dict in `web_arena.py` | ❌ lost on restart |
| Admin key | `ADMIN_KEY` env var, default `gdg-admin-2026` | n/a (env) |
| Custom problems | In-memory | ❌ lost on restart |

**The leaderboard is the only durable state that matters for the demo.**
The fact that it persists in KV (cloud) and not in the judge's local
filesystem is what makes the architecture survive judge restarts.

### 8.2 Non-deployed FastAPI backend (Postgres + Redis)

| Table | Purpose |
|---|---|
| `users` | username, email, password_hash (bcrypt), is_admin, rating, created_at |
| `problems` | slug, title, difficulty, description, time_limit_ms, memory_limit_kb, created_by, created_at |
| `test_cases` | problem_id, input, expected_output, is_sample, is_public, weight |
| `contests` | name, description, start_at, end_at, is_active, created_by |
| `contest_problems` | contest_id, problem_id, position, score |
| `contest_participants` | contest_id, user_id, joined_at, total_points |
| `submissions` | user_id, problem_id, contest_id, language, code, mode, status, runtime_ms, memory_kb, score, created_at, finished_at |
| `submission_results` | submission_id, testcase_id, status, runtime_ms, memory_kb, stdout, stderr, compile_output |

**Indexes:** `user_id`, `problem_id`, `contest_id`, `status` on submissions
(all hot-path filter columns).

**Redis keys:**
- `contest:{id}:leaderboard` (ZSET, score=points, member=user_id)
- `contest:{id}:solve_times` (ZSET, score=-seconds, member="{user_id}:{problem_id}")
- `rq:submissions` (RQ queue, LIST)
- `algobattle:pubsub:*` (pub/sub channels for WebSocket)

---

## 9. Observability

- **Prometheus multiproc exporter** in the Worker sidecar on :9100
- **`structlog`** structured logging in the worker
- **APScheduler** logs the stuck-submission checker run
- **Cloudflare Worker logs** (`wrangler tail`) for proxy traffic

**What's missing:** no centralized log aggregation, no alerting, no
uptime monitoring. For a class demo this is fine; for a real product
you'd want Sentry + Grafana + a status page.

---

## 10. Performance and limits

| Resource | Limit | Why |
|---|---|---|
| Per-submission code length | 100 KB | Pydantic cap; prevents DoS via huge code |
| Per-testcase stdout/stderr | 8 KB | Cap before DB write; prevents DoS via huge output |
| Per-submission CPU time (Python) | 3 s wall | Sandbox `RLIMIT_CPU` |
| Per-submission CPU time (C++/Java) | 10 s wall | Includes compile time |
| Per-submission memory | 256 MB (configurable per problem) | `RLIMIT_AS` |
| Per-submission output | 1 MB | `RLIMIT_FSIZE` |
| Submissions per IP | 30/min | slowapi rate limit on `/submissions` |
| API workers | 2 (gunicorn) | Small-scale default |
| RQ workers | 2 (configurable) | Stateless, scale by adding pods |
| Worker HTTP timeout (Judge0 poll) | 15 s | `judge0_timeout_seconds` |

---

## 11. Problems encountered and mitigations

The complete issue log is in `ISSUES.md`. Highlights, in order of
severity:

### Today's session (Part E, the most important recent ones)

| # | Problem | Mitigation | Status |
|---|---------|-----------|--------|
| E1-1 | **IDOR on submission read** — any logged-in user could read any other user's submission code + stderr | Added `get_by_id_for_user()` returning 404 (not 403) to avoid leaking existence | ✅ Fixed |
| E1-2 | **SQL-injection-shaped pattern in stuck-submission checker** — hand-built `IN (...)` string in raw `text()` SQL | Rewrote with `select().where(status.notin_(TERMINAL_STATUSES))` using async ORM | ✅ Fixed |
| E1-3 | **Silent Judge0 → unsandboxed local-judge fallback in production** — when Judge0 was down, user code ran in an unsandboxed subprocess on the API host | Added `judge_allow_local_fallback` config; `@model_validator` **forces it to False in production**; Judge0 outage now → `INTERNAL_ERROR` instead of unsafe fallback | ✅ Fixed |
| E1-4 | **Default JWT secret shipped in production** — anyone with repo access could forge tokens | `@model_validator` refuses to boot in production with `dev-secret-change-me`; clear error message | ✅ Fixed |
| E1-5 | **Fire-and-forget `create_task` bug** — `judge_submission` called from the FastAPI event loop scheduled the grading coroutine but never awaited it; the request could return and cancel the grading | `judge_submission` now raises if called from a running loop; removed `run_in_executor` path from the router; production always goes through the RQ queue | ✅ Fixed |
| E1-bonus | **`/run` endpoint identical to `/submit`** — both ran all hidden test cases | `/run` now forces `mode="test"`; worker filters testcases by mode | ✅ Fixed |
| E6 | **Live site was returning 502** (`judge_backend_unreachable`) because `TUNNEL_URL` pointed to an offline Codespace | Started local judge + Cloudflare quick tunnel + updated `wrangler secret put TUNNEL_URL`. Live submission `DakshLive` got `AC 3/3` on two-sum. | ✅ Working |
| E5 | **Quick-tunnel URL rotates on every restart** | Need a named tunnel for stability (documented in `vps-setup.md` §5) | ⚠️ Open |

### Earlier sessions (Parts A-D, condensed)

| # | Problem | Mitigation |
|---|---------|-----------|
| A1-1/2 | `preexec_fn` rlimits + SIGALRM don't work on macOS | Switched to `proc.wait(timeout)` + threading.Timer wall-clock kill |
| A1-6 | No pre-exec memory cap → memory bomb OOM-killed by OS | `RLIMIT_AS` in `preexec_fn` + live RSS monitor thread |
| A1-7 | No CPU-time enforcement → unfair ranking under load | `RLIMIT_CPU` (SIGXCPU → TLE) + `getrusage` for real `cpu_time_ms` |
| A1-8 | Output flood could hang or fill disk | `RLIMIT_FSIZE` (SIGXFSZ → OLE) |
| A1-10 | **Java JVM dies in containers** — "Could not reserve enough space for 262144KB object heap" | Gave Java 2 GB `RLIMIT_AS` while capping heap with `-Xmx256m -XX:MaxMetaspaceSize=128m -XX:ReservedCodeCacheSize=64m`; real RSS ~35 MB |
| A1-11 | C++/Java false TLE under concurrent load | Compiled languages get 10 s wall budget (Python 3 s) |
| D1 | Frontend was a generic dark theme with no visual hierarchy | Three-tier color system, LeetCode-orange accent, custom scrollbars, animations, polished empty states |
| D6 | Worker `/api/*` proxy buffered SSE | SSE routes pass `upstream.body` through as a real stream |
| D7 | Worker returned 530/error on transient tunnel failures | Retry + KV fallback for `/health` and `/api/leaderboard` |

### Known open issues (Part E, not yet fixed)

| # | Problem | Why open |
|---|---------|----------|
| E2-1 | No contest time-window or participation check on submit | Out of scope of the E1 brief |
| E2-2 | CORS `allow_origins=["*"]` with credentials — silently rejected by Starlette | Out of scope; needs env-driven override |
| E2-3 | Worker runs in API process — no separate worker service in `infra/` | The deployed architecture uses `web_arena.py` only; the FastAPI backend isn't the live path |
| E2-4 | `/api/health` returns 404 from the proxy — the route exists on the Worker but not on `web_arena.py` at that path | Worker swallows the 404 and returns graceful 502; semantics are wrong but UX is acceptable |
| E2-5 | **75 pre-existing test failures** in this Python 3.14 + FastAPI combo | `_IncludedRouter` stubs don't expand → router-level tests 404. Not caused by E1 fixes. |
| E2-6 | Quick-tunnel URL rotates on restart | Need named tunnel |
| E2-7 | `passlib[bcrypt]>=1.7.4` is unmaintained | Works for now; will break on a future bcrypt release |

---

## 12. The "where do I host this for free" saga

| Date | Question | Answer |
|------|----------|--------|
| Day 1 | Where do I publish the judge on Google Cloud for free? | Tried Cloud Run (sleeps, kills a worker), then GCE e2-micro (1 GB too tight for the JVM), then concluded: **the strongest path is the laptop + Cloudflare Tunnel, not a server** |
| Day 2 | Can't I just run it all in the website (in-browser)? | Pyodide for Python works; for C++/Java it's heavy. But: **loses the system-design story GDG wants** — a strong backend > a slick client-side hack |
| Day 3 | "I should show them GitHub Codespace in the demo and say: if you want it working every time, you can pay and do it" | **This is the right answer.** Show the architecture, show it working live on the laptop, document the always-on paths (Oracle, Azure for Students, VPS), let them pick |
| Day 4 | Oracle needs a credit card; DigitalOcean left the Student Pack on July 31, 2026; Fly.io killed its free tier in Oct 2024; GCP e2-micro needs a card for the Free Trial | Best card-free always-on option for students: **Azure for Students** ($100 credit, always-free services, renewable yearly). Best card-free always-on option for non-students: **any $4-5/mo VPS (Hetzner, Vultr)** |

**For the demo today:** laptop + quick tunnel. **For 24/7 afterwards:** apply for Azure for Students, then run the same `web_arena.py` in Docker on the Azure VM with a named tunnel.

---

## 13. The 5-bug audit summary (the most important recent work)

The audit of `backend/app/` on Aug 29 found 5 real bugs that would block
the system from being safely deployable to a public environment. All 5
are fixed in commit `6ee1938` and verified in this session. The audit
also found 7 other open issues (Part E2) that are documented but not
fixed.

**The fix verification:**
- IDOR: `get_by_id_for_user` raises 404 (not 403) on cross-user access;
  both `get_submission` and `get_results` use it.
- SQLi-pattern: `checker.py` rewritten with `select().where(status.notin_())`
  using the async ORM; no raw SQL.
- Unsafe fallback: `judge_allow_local_fallback` defaults to True in
  dev/test, forced to False in production by `@model_validator`.
- Default JWT secret: `@model_validator` raises at startup in production
  with the default value.
- Fire-and-forget: `judge_submission` now raises if called from a
  running event loop; router no longer uses `run_in_executor`.

All 5 fixes are minimal, surgical, and don't change the public API.

---

## 14. What to do next (priorities)

1. **For the demo:** the live site is working at
   `https://algobattle-arena.dakshx.workers.dev/`. Verify by submitting
   a solution. Keep the two background processes (`s0yclmiq` judge,
   `s1i5hgre` tunnel) running.
2. **Stop the demo:** `kill_shell s0yclmiq` and `kill_shell s1i5hgre`.
3. **For production:** apply for Azure for Students (no card, $100
   credit) → run `web_arena.py` in Docker on the Azure VM → set up a
   **named** Cloudflare tunnel (so the URL doesn't rotate) → point the
   Worker at the named tunnel once.
4. **For code quality:** fix the 7 open issues in Part E2 (CORS, contest
   time-window check, leaderboard reconciliation sweeper, the 75
   pre-existing test failures).
5. **For the 5-bug audit to actually matter:** deploy the FastAPI
   backend (not just `web_arena.py`) and run the E1 fixes there — the
   current live path is `web_arena.py` which doesn't have the IDOR, the
   fire-and-forget, or the Judge0 fallback at all.

---

## 15. File map (where to look for what)

| Topic | File |
|---|---|
| FastAPI app factory | `backend/app/main.py` |
| Config + production-safety validator | `backend/app/config.py` |
| JWT + bcrypt | `backend/app/core/security.py` |
| Auth deps (CurrentUserId, AdminUserId) | `backend/app/deps.py` |
| Custom exceptions + handlers | `backend/app/core/exceptions.py` |
| User model + service + router | `backend/app/modules/users/` |
| Problem model + service + router | `backend/app/modules/problems/` |
| Contest model + service + router | `backend/app/modules/contests/` |
| Submission model + service + router | `backend/app/modules/submissions/` |
| Submission judge task (the real one) | `backend/app/modules/submissions/tasks.py` |
| Stuck-submission sweeper | `backend/app/modules/submissions/checker.py` |
| Judge0 client | `backend/app/modules/submissions/judge_client.py` |
| Leaderboard (Redis ZSET) | `backend/app/modules/leaderboard/` |
| WebSocket router (live updates) | `backend/app/core/ws_router.py` |
| Live-deployed judge (the simple one) | `backend/sandbox/web_arena.py` |
| Live-deployed sandbox runner | `backend/sandbox/sandbox_runner.py` |
| Live-deployed judge Docker image | `backend/sandbox/Dockerfile` |
| Cloudflare Worker source | `backend/sandbox/deploy/worker/index.js` |
| Worker config (binding to assets + KV) | `backend/sandbox/deploy/worker/wrangler.toml` |
| 24/7 deploy guide | `backend/sandbox/deploy/vps-setup.md` |
| Codespaces deploy guide | `backend/sandbox/deploy/CODESPACES.md` |
| Frontend (single-file, no framework) | `backend/sandbox/deploy/public/index.html` |
| All issues, ever | `ISSUES.md` |
| This document | `PROJECT_OVERVIEW.md` |

---

## 16. One-paragraph summary for a stranger

AlgoBattle is a competitive coding platform (LeetCode/Codeforces style)
that runs user-submitted code in a sandboxed subprocess, grades it against
hidden test cases, and ranks participants on a live leaderboard. It's
deployed as a Cloudflare Worker (frontend + API proxy + leaderboard KV)
in front of a Python sandbox backend exposed via a Cloudflare Tunnel —
the worker handles the static parts at the edge, the sandbox runs where
it can actually execute code. The heavier FastAPI + Postgres + Redis + RQ
+ Judge0 backend exists in the repo and is the natural migration target
for production scale. The Aug 29, 2026 debugging session found and fixed
5 real security/correctness bugs in the FastAPI backend, brought the live
site back online via a local laptop + Cloudflare quick tunnel, and
documented the full "where to host this for free" decision matrix (Oracle
needs a card, DigitalOcean's student pack ended July 2026, Azure for
Students is the best card-free always-on option).
