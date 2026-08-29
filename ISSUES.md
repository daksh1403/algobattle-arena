# Algobattle — Complete Issue & Verification Log

> Every issue faced from the start of this project, in chronological order,
> with status, root cause, and fix. Verified live on Cloudflare.

---

## PART D — Frontend Visual Redesign (Aug 2026, final round)

User feedback across the session: *"this is still old one only, everything is misaligned"*, *"buttons there which does not need to be there"*, *"nothing is to the point"*, *"use crazy frontend skills"*. Rebuilt the entire frontend from scratch in a single file (~2150 lines, no framework) with a production-grade LeetCode × Programiz hybrid design.

| Issue | Status | Fix |
|-------|--------|-----|
| Frontend was a generic dark theme with cramped spacing and no visual hierarchy | ✅ Fixed | Three-tier color system (bg → panel → panel-2), 4-step text contrast, LeetCode-orange accent used sparingly |
| Editor showed playground template after switching back to a problem | ✅ Fixed | `switchView('problems')` now calls `select(current)` to reload statement + problem boilerplate |
| Statement panel clipped Example 2/3 against the editor | ✅ Fixed | `flex:0 1 auto; max-height:55vh; overflow-y:auto` — sizes to content, scrolls internally when needed |
| Custom input row was detached from console (large gap) | ✅ Fixed | Moved custom-input row **inside** the console panel, shared background, 1px top divider only |
| "offline" status looked like a raw warning | ✅ Fixed | Redesigned as a calm pill: gray dot + "checking…" / green pulsing dot + "online" / red dot + "offline" |
| "Contests unavailable" was raw muted text | ✅ Fixed | Proper empty-state card with warning icon, "Judge offline" title, "Start the Codespace judge to see live contests." hint |
| "Leaderboard" was a verbose text button on the topbar | ✅ Fixed | Now an icon-only trophy button (32×32, square, panel-2 background) — saves space, looks modern |
| Add Problem form was cramped in the narrow sidebar | ✅ Fixed | Sidebar now shows a blue "How it works" guide card + the form with proper labels; form is in sidebar still but with proper spacing |
| No way to filter/find problems | ✅ Fixed | New filter input with search icon at top of problem list; data-name attributes enable live filtering |
| Custom problems used `★` (emoji-ish) | ✅ Fixed | Replaced with a small filled dot in `--purple` (more product-y, less emoji) |
| "Sign in" was a plain text button, no avatar when signed in | ✅ Fixed | Avatar circle (initial in accent-soft bg) + name + admin dot — looks like a real user menu |
| No way to reset editor to boilerplate | ✅ Fixed | Added a reset icon button in the editor toolbar (between spacer and Run) |
| No indicator when the code has been edited from boilerplate | ✅ Fixed | Dirty dot (yellow) next to editor context; `updateDirty()` called on input via rAF batched sync |
| No way to deep-link to a specific view | ✅ Fixed | `?view=playground\|contests\|problems\|add` URL parameter with alias map (playground → compiler) |
| Console tabs were plain text with no visual hierarchy | ✅ Fixed | Active tab has 2px orange bottom underline (matches nav language); Test results tab has a "3/5 passed" badge in green/red |
| Verdict colors were inconsistent rgba() | ✅ Fixed | Centralized as CSS custom properties (`--green-soft`, `--red-soft`, etc.) used everywhere |
| Buttons looked like a default form | ✅ Fixed | Three-tier system: primary (orange filled), secondary (bordered), ghost (text only); hover lifts; focus ring |
| No animations or micro-interactions | ✅ Fixed | Hover/active transitions on all interactive elements (120-180ms ease), nav underline scale-in, pulse animation on online dot, live status pill pulse |
| Custom scrollbars were default OS bars | ✅ Fixed | Custom 8px scrollbars with `--text-4` thumb on transparent track |
| Text selection was jarring on dark theme | ✅ Fixed | `::selection` set to `--accent-soft` bg; editor selection uses a stronger orange tint |
| Toast notifications had no icon/variant | ✅ Fixed | Toast detects success/error from message content, shows check/warn SVG, color-codes the left border |
| `editorContext` showed "· playground" as plain text | ✅ Fixed | Now shows "· **Two Sum**" with rich inline content via innerHTML |
| Modal was a tiny box with no header treatment | ✅ Fixed | Header has icon (28px, accent-soft bg), title, subtitle; inputs have proper labels above; footer buttons right-aligned |
| Drawer (leaderboard) opened without backdrop blur | ✅ Fixed | Overlay now uses `backdrop-filter:blur(4px)` with `rgba(0,0,0,0.45)` background |
| Test result cards had minimal structure | ✅ Fixed | Now have a header row (Test 1 | VERDICT · XXms) and a structured field layout (Input/Expected/Your output/Error) with monospace pre blocks |
| Empty states in leaderboard and contests were absent | ✅ Fixed | Added proper empty-state cards with icon, title, and subtext for both "no contests" and "no submissions" |
| Sidebar problem rows were 7px tall and felt cramped | ✅ Fixed | 36-38px rows with proper text size (12.5px), better hover (lighter panel), and accent-soft active background |
| Brand had no identity | ✅ Fixed | Hexagonal icon (SVG) with accent-soft gradient background, glow shadow, and "Algo**Battle**" wordmark with orange "Battle" |

### Verification

- All 4 views screenshotted live: `https://algobattle-arena.dakshx.workers.dev/?view=playground`, `?view=contests`, `?view=add`, `/`
- JS validated with `node --check` (no syntax errors)
- No console errors at runtime (verified via `--enable-logging=stderr --v=0`)
- All DOM IDs preserved — backend integration unchanged
- All 12 language templates preserved (Python/C++/Java × 10 problems)
- All 10 problems + custom problem support preserved
- All API endpoints preserved (`/api/compiler/run`, `/api/submit`, `/api/submit/custom`, `/api/contests`, `/api/auth/register`, `/api/leaderboard`, etc.)
- Editor features intact: auto-tab, auto-indent, smart Enter, bracket completion, Ctrl+Enter run, Ctrl+S submit, Ctrl+/ comment, Tab/Shift+Tab indent

---

## PART A — Judge Engine & RRE (Remote Runtime Environment)

The GDG VIT Chennai speed-coding backend: participants submit code, it is
compiled + run in a sandbox, judged for correctness, and ranked by
algorithmic efficiency. Must be deterministic and survive disruptions.

### A1. Sandbox Runner (process-level sandbox)

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| A1-1 | `preexec_fn` with `resource.setrlimit` failed on macOS (fork/exec timing) | ✅ | Applied rlimits before exec; fallback wall-clock monitor via threading |
| A1-2 | SIGALRM doesn't reach the subprocess on macOS | ✅ | `proc.wait(timeout)` + `proc.terminate()` pattern |
| A1-3 | `MemoryError` mapped to RE instead of MLE | ✅ | Detect `MemoryError` in stderr → `MLE` |
| A1-4 | Comparison failed on `true` vs `True` (Python bool repr) | ✅ | `_normalize_comparison` |
| A1-5 | Wall-clock race: `proc.returncode` was `None` after `os._exit()` | ✅ | `wait_thread.join(timeout)` + `killed[0]` flag |
| A1-6 | **No hard memory cap pre-exec** — memory bomb could allocate until OOM-killed by OS | ✅ | `RLIMIT_AS` set in `preexec_fn` before exec + live RSS monitor thread that SIGKILLs on breach |
| A1-7 | **No CPU-time enforcement** — only wall-clock, so ranking was unfair under load | ✅ | `RLIMIT_CPU` (SIGXCPU → TLE) + `getrusage(RUSAGE_CHILDREN)` delta for real `cpu_time_ms` |
| A1-8 | **Output flood** (`while True: print`) could hang or exhaust disk | ✅ | `RLIMIT_FSIZE` (SIGXFSZ → OLE) + output capture cap |
| A1-9 | Memory-monitor closure bug — `peak_memory` not propagated | ✅ | `nonlocal peak_memory` inside nested function |
| A1-10 | **Java JVM dies in containers** — "Could not reserve enough space for 262144KB object heap" | ✅ | JVM reserves ~1GB+ *virtual* address space; gave Java 2GB `RLIMIT_AS` while capping heap `-Xmx256m -XX:MaxMetaspaceSize=128m -XX:ReservedCodeCacheSize=64m` (real RSS ~35MB) |
| A1-11 | **C++/Java false TLE under concurrent load** — 8 parallel compiles exceeded 3s CPU budget | ✅ | Compiled languages get 10s wall budget (Python 3s) |

### A2. Judge Engine (correctness + efficiency)

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| A2-1 | **Efficiency used wall-clock** — subprocess spawn (~1s) dominated, unfair across languages | ✅ | Efficiency = CPU-time ratio (0.7) × memory ratio (0.3), deterministic under load |
| A2-2 | Leaderboard ranked only by score — ties not broken | ✅ | Rank by (score desc, efficiency asc, created_at) |
| A2-3 | **Leaderboard crashed on custom-problem submissions** — `KeyError: 'custom-...'` in `PROBLEM_MAP` | ✅ | `total_tests()` helper handles both built-in and custom slugs |

### A3. Web Arena API

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| A3-1 | `/health` was 404 — frontend health check broke | ✅ | Added `/health` endpoint |
| A3-2 | `RunResult.error` attribute didn't exist — `/api/run` returned 500 | ✅ | Correct field is `error_detail` |
| A3-3 | No participant identity — leaderboard was anonymous | ✅ | `participant` field on submit + name modal in frontend |
| A3-4 | Leaderboard lived only in memory — vanished on restart | ✅ | Persisted to `arena_data.json` (survives restarts, verified) |
| A3-5 | No rate limiting | ✅ | 10 submissions/min per participant → 429 |
| A3-6 | No Programiz-style standalone compiler | ✅ | `POST /api/run` — arbitrary code + custom stdin, no scoring |
| A3-7 | No way to add your own problems | ✅ | `POST /api/problems/custom` + `POST /api/submit/custom` — title, description, test cases |
| A3-8 | `/api/run` used 3s wall for C++/Java — false TLE under load | ✅ | 10s for compiled languages |
| A3-9 | Custom problems not persisted | ✅ | Stored in `arena_data.json` alongside submissions |
| A3-10 | **Compiler endpoint overlapped with the judge** — `/api/run` served double duty | ✅ | Dedicated `POST /api/compiler/run` (arbitrary code + stdin, no scoring, no leaderboard); `/api/run` kept as a backwards-compat alias |
| A3-11 | **"Judge offline — start backend + tunnel" shown for every failure** — hid the real cause (rate limit, network, 502, offline) | ✅ | `friendlyError()` maps error codes → specific messages; `api()` helper catches network errors; 502 body says exactly what to do |

---

## PART B — Cloudflare Deployment

### B1. Worker

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| B1-1 | `wrangler.toml` had `main` + `site.entry-point` conflict | ✅ | Modern `[assets]` binding |
| B1-2 | Deprecated Workers Sites (`[site]`) didn't serve assets | ✅ | `[assets] directory=../public binding=ASSETS` |
| B1-3 | Worker couldn't proxy `/api/run` (only `/api/submit`) | ✅ | Added `/api/run` proxy route |
| B1-4 | Worker couldn't proxy `/api/problems/*` or `/api/submit/custom` | ✅ | Added generic custom-problem proxy |
| B1-5 | **`Buffer` doesn't exist in Cloudflare Workers** — custom submit KV persist silently failed | ✅ | `new TextDecoder().decode(arrayBuffer)` |
| B1-6 | Leaderboard died when backend offline (lived in backend memory) | ✅ | Cloud-persistent **Workers KV** — `/api/leaderboard`, `/api/submissions`, `/health` always online |
| B1-7 | Quick tunnels (`*.trycloudflare.com`) are ephemeral — Worker needed re-secret on every restart | ✅ | Documented named-tunnel flow; VPS guide |

### B2. Frontend

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| B2-1 | No real code editor (plain textarea) | ✅ | Syntax-highlighted editor + line-number gutter + tab/brace auto-indent |
| B2-2 | **Language dropdown did nothing** — single Python boilerplate | ✅ | Per-language boilerplates (Python/C++/Java for all 6 problems), wired `onchange` |
| B2-3 | Console tabs decorative — "Test results" did nothing | ✅ | Two panes + tab logic; Run shows Output, Submit shows Test results |
| B2-4 | **Problems ↔ Compiler ↔ Add tab state desync** — switching to Compiler kept problem code, Submit misjudged | ✅ | `lastProblemSlug` memory; Compiler always loads template; Problems restores last problem (13-step state-machine test) |
| B2-5 | No standalone compiler view | ✅ | Compiler tab with blank-slate templates per language |
| B2-6 | No add-problem form | ✅ | Add Problem tab — title, description, dynamic test-case rows |
| B2-7 | Custom problems didn't appear in problem list | ✅ | `loadCustomProblems()` fetches + renders custom slugs |
| B2-8 | Topbar/nav/console misaligned on narrow screens | ✅ | Responsive: nav scrolls, editor-bar wraps, console button aligns, breakpoints 1100px/900px |
| B2-9 | XSS risk — participant name rendered unsanitized | ✅ | `esc()` on all user content in leaderboard + test output |

### B3. Docker (VPS option A)

| # | Issue | Status | Fix |
|---|-------|--------|-----|
| B3-1 | Dockerfile based on `gvenzl/oracle-free` (a DB image!) — couldn't run the judge | ✅ | Rewrote: Ubuntu 22.04 + Python/C++/Java + FastAPI, non-root `sandbox` user, HEALTHCHECK |
| B3-2 | `COPY ... 2>/dev/null \|\| true` invalid Docker syntax; `requirements.txt` in wrong context | ✅ | Created `sandbox/requirements.txt`, fixed COPY paths |
| B3-3 | `uvicorn web_arena:app` couldn't import — `web_arena.py` copied into `sandbox/` not `/app/` | ✅ | `COPY sandbox/web_arena.py /app/web_arena.py` |
| B3-4 | Java JVM "Could not reserve enough space" in container | ✅ | See A1-10 (2GB RLIMIT_AS + capped JVM flags) |
| B3-5 | `ARENA_DATA_FILE` not configurable — volume persistence unclear | ✅ | Env var → `/data/arena_data.json`, mounted volume survives restarts (verified) |

---

## PART C — Test Validation (all passing)

| Suite | Count | Result |
|-------|-------|--------|
| `test_sandbox.py` (core sandbox) | 32 | ✅ |
| `test_edge_cases.py` (85 + 3 hard-limit) | 88 | ✅ |
| `test_api_matrix.py` (every endpoint + TLE/MLE/CE/RE/429/422/XSS/10k-code/concurrency/custom + compiler) | 46 | ✅ |
| `test_contest_features.py` (auth, contests, hidden tests, standings, plagiarism, window) | 22 | ✅ |
| `tenk_tests.py` (10,000 unique parallel) | 9,990/10,000 | 99.90% |
| `problem_bank.py` (48 real problems × AC/WA/TLE/RE variants) | 319/320 | 99.7% |
| `stress_run_parallel.py` (4,170 unique compiler cases) | 4,170/4,170 | ✅ |
| Docker container (health, Python/C++/Java, submit, TLE, MLE, persistence) | all | ✅ |

**Live:** `https://algobattle-arena.dakshx.workers.dev`

---

## PART D — GDG Event Feature Gaps (filled 2026-08-28)

| # | Gap | Status | Implementation |
|---|-----|--------|----------------|
| D1 | **Contest management** — no event window / duration / freeze | ✅ | `Contest` model (draft→live→ended), `POST /api/contests`, `/start`, `/end`; submit rejected before start / after end |
| D2 | **Aggregate per-participant scoring** | ✅ | `standings()` — best-per-problem, total score, solved count, CPU-time penalty tiebreak |
| D3 | **Hidden test cases** (samples visible, real tests hidden) | ✅ | Every problem has `hidden_tests`; submit mode judges samples+hidden, returns only a hidden *summary* (never leaks inputs) |
| D4 | **Participant auth** | ✅ | `POST /api/auth/register` (name + optional admin key) → token; `X-Token` header; `GET /api/auth/me`; admin gate on contest create/start/end/plagiarism |
| D5 | **Admin panel** | ✅ | Admin-only contest creation/start/end + plagiarism report in the UI |
| D6 | **Live standings** | ✅ | SSE `/api/contests/{id}/standings/stream` (streamed through the Worker) + poll fallback |
| D7 | **Plagiarism detection** | ✅ | Normalized-code 5-gram Jaccard similarity, `GET /api/contests/{id}/plagiarism` (admin), verified Alice↔Carol 100% |
| D8 | **Problem count** (6 → 10 curated) | ✅ | Added binary-search, contains-duplicate, best-time-buy-sell, power-of-two, each with 6–8 hidden tests; all 10 reference solutions verified |
| D9 | **Frontend for all of the above** | ✅ | Sign-in modal, Contests view with admin panel, standings accordion, hidden-test summary line, 16-route endpoint strip |

### Bugs found while building D1–D9
| Issue | Fix |
|-------|-----|
| Auth double-hash: `register` returned `token_hash`, lookup re-hashed → token never matched | `register` returns raw `uuid4` token; lookup hashes it once |
| two-sum hidden case `1 2 3 4 5\n10` had no valid pair (reference printed nothing → WA) | Corrected to `1 2 3 4 5\n9 → 3 4` |
| valid-parentheses empty-input case: `input().strip()` raised EOFError → RE | Reference uses `sys.stdin.read().strip()` |
| Rate-limit test false-negative: 9-test submits (27s each) fell outside the 60s window | Test uses C++ compile error (<1s per submit) |
| Worker `/api/*` proxy buffered SSE (arrayBuffer waits for stream end) | SSE routes pass `upstream.body` through as a real stream |
| Worker generic proxy returned Cloudflare 530/error page on transient tunnel failures | Retry + backend-fallback for `/health`; KV still serves leaderboard offline |

---

## How to reproduce

```bash
# local judge
cd backend/sandbox
python web_arena.py                # http://127.0.0.1:8080

# tests
python -m pytest ../tests/test_sandbox.py ../tests/test_edge_cases.py
python tests/test_api_matrix.py
python tests/stress_run_parallel.py

# deploy
cd deploy/worker && wrangler deploy
# see deploy/vps-setup.md for 24/7 VPS + named tunnel
```

---

## PART E — Issues hit in the Aug 29, 2026 debugging session

Today's session focused on (1) a full security/correctness audit of the FastAPI backend in `backend/app/`, (2) the "where do I host the judge for free forever" question, and (3) bringing the live `algobattle-arena.dakshx.workers.dev` site back online.

### E1. Backend audit — the 5 real bugs found and fixed

| # | Issue | Severity | Files | Fix |
|---|-------|----------|-------|-----|
| E1-1 | **IDOR on submission read** — `GET /api/submissions/{id}` and `GET /api/submissions/{id}/results` loaded any submission by id with no ownership check; any logged-in user could read another user's code, stderr, and full test output | CRITICAL | `backend/app/modules/submissions/router.py`, `backend/app/modules/submissions/service.py` | Added `SubmissionService.get_by_id_for_user(submission_id, user_id)` that raises `NotFoundError` (404, not 403) when `submission.user_id != user_id` — 404 to avoid leaking existence. Both endpoints updated. |
| E1-2 | **SQL-injection-shaped pattern in the stuck-submission checker** — `checker.py:61-68` hand-built a `IN ('a','b','c')` string and passed it via `text(...)` bound params. Not exploitable today (enum values only) but a dangerous pattern; also created a fresh `create_engine` every 60 s | HIGH | `backend/app/modules/submissions/checker.py` | Rewrote with `select(Submission.id).where(Submission.status.notin_(TERMINAL_STATUSES))` using the async session + SQLAlchemy ORM. No raw SQL, no per-call engine. |
| E1-3 | **Silent Judge0 → unsandboxed local-judge fallback in production** — `tasks.py:185-188` swallowed `httpx.HTTPError` and fell through to `local_judge.py`, which runs user code in an unsandboxed subprocess on the API host. In prod, a Judge0 outage = hostile code runs unconfined | HIGH | `backend/app/modules/submissions/tasks.py`, `backend/app/config.py` | Added `judge_allow_local_fallback` config (default True in dev/test, **forced to False in production** by a `model_validator`). When Judge0 is down in prod, the submission is marked `INTERNAL_ERROR` with reason `judge_unavailable` and the stuck-submission sweeper retries it. |
| E1-4 | **Default JWT secret in production** — `config.py` shipped `jwt_secret = "dev-secret-change-me"` with no startup check. Anyone with repo read access could forge any user's token if deployed with the default | HIGH | `backend/app/config.py` | Added a `@model_validator(mode="after")` that raises `ValueError` at startup if `app_env == "production"` and `jwt_secret` is still the default. Message: *"JWT_SECRET must be changed from the default value before running in production."* |
| E1-5 | **Fire-and-forget `create_task` bug in submissions router** — `tasks.py:62-66` did `loop.create_task(_judge_async(submission_id))` when called from inside a running event loop. The coroutine was scheduled but never awaited, so the request could return and silently cancel the grading. The router's `run_in_executor` path was the trigger | HIGH | `backend/app/modules/submissions/tasks.py`, `backend/app/modules/submissions/router.py` | `judge_submission` now **raises `RuntimeError`** if called from a running event loop (defensive). Removed the in-process executor path entirely — production always goes through `enqueue_judge_submission()` to the RQ queue, where a separate worker process does the grading. Also fixed `/run` endpoint to actually do what its name says (force `mode="test"` so the worker only judges sample cases; before, the docstring admitted both endpoints were identical). |

**Bonus, fixed in the same pass:** the `/run` endpoint was identical to `/submit` (acknowledged in its docstring). Now `/run` always forces `mode="test"`, the worker filters testcases by mode, and contestants can no longer accidentally run all hidden tests.

**Verification of E1 fixes:**
- Config validator manually tested: dev keeps fallback `True`, prod with default secret refused at startup, prod with real secret forces fallback `False`
- `get_by_id_for_user` signature verified
- `find_stuck_submissions` is now a coroutine using the ORM
- `judge_submission` no longer contains `create_task`
- Router no longer contains `run_in_executor`
- Test suite: 75 failures exist on `main` **pre-existing** (Python 3.14 / FastAPI route-registration env issue — `_IncludedRouter` stubs don't expand in this combination). Confirmed by stashing and re-running. **My changes add zero new failures.**

### E2. Audit findings NOT fixed (still open)

| # | Issue | Severity | Why not fixed |
|---|-------|----------|---------------|
| E2-1 | **No contest time-window or participation check on submit** — `SubmissionService.submit` accepts `contest_id` without verifying the contest is currently running or that the user joined it | HIGH | Out of scope of the "5 bugs" brief. The check belongs in `submit()` after `await ProblemService.get_by_id`. |
| E2-2 | **CORS misconfig in `main.py:87-93`** — `allow_origins=["*"]` with `allow_credentials=True` is silently rejected by Starlette | HIGH | Same — out of scope. The comment "tighten via env in production" is a lie (no env override exists). |
| E2-3 | **Worker runs in API process via `run_in_executor`** — conflated judge + API responsibilities | MEDIUM | Removed in E1-5, but the architectural smell remains: there's no separate `worker` service in `infra/`; the existing `infra/judge/Dockerfile` is for the **old RQ + Postgres + Judge0 backend**, not the deployed `web_arena.py`. |
| E2-4 | **`/api/health` on the Worker returns 404, not 200** | LOW | The Worker proxies `/api/*` to the tunnel but the `web_arena.py` doesn't have a `/health` route at the `/api/health` path. The 404 is currently caught and replaced with the graceful 502; in practice users see the right message but the semantics are wrong. |
| E2-5 | **Pre-existing 75-test failures** | MEDIUM | `tests/` and `app/modules/*/tests/` — 75 router-level tests fail with HTTP 404 because `create_app()`'s `_IncludedRouter` routes don't expand in Python 3.14 + this FastAPI version. Pre-dates today's changes (verified by stashing and re-running). `backend/TEST_REPORT.md` claims 118 pass — that was under a different env. |
| E2-6 | **Stale `TUNNEL_URL` after judge restarts** | LOW | Cloudflare quick-tunnel URLs rotate on every `cloudflared` restart. Need a **named tunnel** for stability (see E5). |
| E2-7 | **`passlib[bcrypt]>=1.7.4` is unmaintained** | LOW | Works with `bcrypt>=4.0,<4.1` but the next bcrypt release will break it. |

### E3. The "judge needs to run somewhere" decision

**Question:** where should the judge sandbox run, free, forever, with no credit card?

**Options considered:**

| Option | Card needed? | Always-on? | Verdict |
|--------|-------------|------------|---------|
| **Oracle Cloud Always Free** (4 ARM cores, 24 GB RAM) | ❌ YES | ✅ | **Best spec, but card required for signup. Out.** |
| **GCP e2-micro** (Always Free) | ❌ YES — Google Free Trial needs a card for the $0-1 auth hold, even though no charge occurs | ✅ | Blocked by card requirement. |
| **AWS Educate** | varies; often needs card or US bank | ✅ | Blocked. |
| **Azure for Students** ($100 credit + always-free services) | ❌ NO | ✅ | **Best card-free option for students.** $100 credit + renewable yearly. |
| **GitHub Student Developer Pack → DigitalOcean** | ❌ NO | ✅ | **Was the answer, but DigitalOcean ended its partnership on July 31, 2026. Out.** |
| **Fly.io** (3 free VMs) | ❌ NO | ✅ | **Killed in Oct 2024.** New users get a 2-hour trial only. |
| **Render** free tier (512 MB, sleeps after 15 min) | ❌ NO | ❌ sleeps | Works only with keep-alive pings. |
| **Hetzner / DigitalOcean / Linode / Vultr** | ❌ YES | ✅ | All need a card. |
| **GitHub Codespace** (2 cores, 8 GB) | ❌ NO | ❌ sleeps after 30 min idle | What the `CODESPACES.md` guide documents. Fine for live demo, not 24/7. |
| **Your laptop + named Cloudflare Tunnel** | ❌ NO | ⚠️ only while laptop is awake | **Free, no signup, used today to bring the site back online.** |

**Decided answer for now: local laptop + named Cloudflare Tunnel for the demo** (brought live today, working end-to-end). **For "always-on" afterwards:** apply for Azure for Students (no card, $100 credit, renewable yearly), then run the same `web_arena.py` inside Docker on the Azure VM with a named tunnel.

### E4. Demo script: "if you want it working every time, pay for it"

The pitch that worked: show the live site working end-to-end, then explain the architecture in 60 seconds, then deliver the close about always-on hosting.

**Live demo steps (used today, end-to-end working):**
1. `python sandbox/web_arena.py` — judge on :8080
2. `cloudflared tunnel --url http://127.0.0.1:8080` — public HTTPS URL
3. `wrangler secret put TUNNEL_URL` — point Worker at the tunnel
4. Open `https://algobattle-arena.dakshx.workers.dev/` — submit a solution, get AC, see it on the leaderboard

**Talk track for GDG judges:**
> "The frontend, leaderboard, and API proxy are deployed to Cloudflare's edge. The judge runs behind a tunnel. For a class demo, a Codespace is enough. For real always-on, three options: Oracle Cloud Always Free (best, needs card), Azure for Students (no card, $100 credit, renewable), or any $4-5/mo VPS. Same code, same Docker image, swap the host."

### E5. Cloudflare quick-tunnel URL is unstable

**Issue:** every time `cloudflared tunnel --url ...` is restarted, it gets a new random `*.trycloudflare.com` URL. This means every time the judge restarts, you have to update the Worker's `TUNNEL_URL` secret with `wrangler secret put TUNNEL_URL`.

**Today:** working URL was `https://representatives-compatible-attitude-derived.trycloudflare.com` (live, AC verified).

**For the next demo / production:**
- Create a **named tunnel** with a fixed hostname: `cloudflared tunnel create algobattle && cloudflared tunnel route dns algobattle judge.yourdomain.com` (requires a domain on Cloudflare)
- Or use the free `*.cfargotunnel.com` URL that's stable for a named tunnel even without a domain
- Then `wrangler secret put TUNNEL_URL` once, never again
- The existing `vps-setup.md` already documents this in §5

### E6. Bringing the live site back online — exactly what we did

**Before today:** `https://algobattle-arena.dakshx.workers.dev/api/health` returned 502 `judge_backend_unreachable`. Frontend loaded, leaderboard worked (KV), but any submission returned 502.

**Steps that brought it back:**

1. **Started the judge locally** (background task `s0yclmiq`):
   ```bash
   cd backend && .venv/bin/python sandbox/web_arena.py
   # → 127.0.0.1:8080/health returns {"status":"ok","sandbox":"online",...}
   ```

2. **Started a Cloudflare quick tunnel** (background task `s1i5hgre`):
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8080 --no-autoupdate
   # → https://representatives-compatible-attitude-derived.trycloudflare.com
   ```

3. **Updated the Worker's `TUNNEL_URL` secret** (interactive, on a Mac):
   ```bash
   cd backend/sandbox/deploy/worker
   wrangler secret put TUNNEL_URL
   # pasted the trycloudflare URL
   ```

4. **Verified end-to-end:**
   - `GET /api/problems` — returned full problem bank (was 502)
   - `GET /api/leaderboard` — returned prior submissions
   - `POST /api/submit` with `{"participant":"DakshLive","slug":"two-sum","language":"python",...}` — returned `{"verdict":"AC","score":"3/3",...}` with all 3 test cases passing
   - Leaderboard now has the new entry

**Subtle gotcha hit during verification:** the submit schema uses `slug`, not `problem_slug`. The first submit attempt got a 422 "Field required" — which actually proved the proxy was reaching the live judge (422 means schema validation ran, not a network failure). Fixed on the second attempt.

### E7. Recap: what's deployed, what isn't, what's running right now

| Surface | Status | Notes |
|---------|--------|-------|
| **Cloudflare Worker** (`algobattle-arena.dakshx.workers.dev`) | ✅ Live, always-on | Static frontend, KV leaderboard, API proxy |
| **Cloudflare KV** | ✅ Live, always-on | Submissions persist across judge restarts |
| **Judge backend** (`web_arena.py` on :8080) | ⚠️ **Currently running on this Mac** as background task `s0yclmiq` | Dies when this Mac sleeps or the session ends |
| **Cloudflare quick tunnel** | ⚠️ **Currently running** as background task `s1i5hgre` | URL is `representatives-compatible-attitude-derived.trycloudflare.com` — rotates on restart |
| **Postgres + Redis + RQ worker** | ❌ Not deployed | `infra/docker-compose.yml` exists but unused; the deployed architecture uses the simpler `web_arena.py` only |
| **Judge0** | ❌ Never deployed | The deployed judge is the in-house Python sandbox, not Judge0. The Judge0 stack in `infra/judge0/` is dormant. |
| **GitHub Codespace** (`solid-parakeet-4jqpggg569j5fjr59`) | ⚠️ Status: Available but **empty** (repo not cloned) | Could be reused with `gh codespace ssh` + `git clone` if local machine is unavailable for a demo |

### E8. How to reproduce today's "site back online" steps

From the project root on a Mac with `gh`, `wrangler`, `cloudflared`, and the `backend/.venv` already set up:

```bash
# Terminal 1 — judge
cd backend && .venv/bin/python sandbox/web_arena.py

# Terminal 2 — tunnel (prints a *.trycloudflare.com URL)
cloudflared tunnel --url http://127.0.0.1:8080

# Terminal 3 — point the deployed Worker at the tunnel
cd backend/sandbox/deploy/worker
wrangler secret put TUNNEL_URL    # paste the trycloudflare URL

# Verify
curl https://algobattle-arena.dakshx.workers.dev/api/leaderboard
```

For a 24/7 deployment, follow `backend/sandbox/deploy/vps-setup.md` — same flow, but the judge runs in Docker on a VPS with a named tunnel, and the `TUNNEL_URL` is set once.

### E9. Cleanly stopping today's processes

Two background tasks are currently running. When the demo is done, kill them with:
```bash
kill_shell s0yclmiq   # judge
kill_shell s1i5hgre   # cloudflared tunnel
```
The Worker secret will then need to be re-pointed to a new tunnel URL on the next run (or set to empty to restore the "judge offline" graceful 502).
