# Algobattle — Architecture Diagrams

This document contains comprehensive Mermaid diagrams illustrating the Algobattle system's architecture, data flows, state machines, security model, and data model. These diagrams are the authoritative visual reference for the project.

---

## 1. System Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#4F46E5', 'primaryTextColor': '#fff', 'primaryBorderColor': '#3730A3', 'lineColor': '#6B7280', 'secondaryColor': '#10B981', 'tertiaryColor': '#F59E0B'}}}%%
graph TB
    %% --- Clients ---
    subgraph "Client Layer"
        WEB["🌐 React Frontend\n+ Monaco Editor"]
        VSCODE["⚡ VS Code Extension\n(algobattle.login / .runTests)"]
    end

    %% --- Gateway ---
    subgraph "Gateway / Edge"
        CDN["🌍 CDN\n(CloudFlare / AWS CloudFront)"]
        TRAEFIK["🔀 Traefik\n(HTTPS + Let's Encrypt TLS)"]
        RATE["⚠️ Rate Limit Middleware\n(60 req/min per IP)"]
        CORS["🔒 CORS Middleware\n(frontend origin only)"]
    end

    %% --- API Backend ---
    subgraph "FastAPI Backend (ASGI)"
        API["🚀 FastAPI Application\n(gunicorn -k uvicorn.Worker -w 2)"]
        
        subgraph "FastAPI Modules"
            AUTH["🔐 /auth\n(register, login, JWT)"]
            PROBLEMS["📋 /problems\n(CRUD, list, detail)"]
            SUBMISSIONS["📤 /submissions\n(submit, run, status)"]
            CONTESTS["🏆 /contests\n(lifecycle, register)"]
            LEADERBOARD["📊 /leaderboard\n(scores, rank)"]
            WS["🔄 WebSocket /ws\n(live verdict push)"]
        end
        
        API --> AUTH
        API --> PROBLEMS
        API --> SUBMISSIONS
        API --> CONTESTS
        API --> LEADERBOARD
        API --> WS
    end

    %% --- Data Stores ---
    subgraph "Data Layer"
        REDIS["🟢 Redis 7\n• Sorted Sets: leaderboard\n• List: judge queue\n• Pub/Sub: live updates\n• Hash: session cache"]
        PG["🐘 PostgreSQL 16\n• users\n• problems\n• submissions\n• contests\n• leaderboard"]
    end

    %% --- Worker Layer ---
    subgraph "Judge Worker Layer"
        subgraph "RQ Worker Pool"
            WORKER1["👷 RQ Worker 1\n(--concurrency 4)"]
            WORKER2["👷 RQ Worker 2\n(--concurrency 4)"]
            WORKER3["👷 RQ Worker N\n(--concurrency 4)"]
        end
        
        JUDGE0["�andbox Judge0\n(Docker Container)\n• isolate (IOI sandbox)\n• CPU/cgroup limits\n• No network\n• Per-job tmpfs\n• seccomp: RuntimeDefault"]
        
        WORKER1 --> JUDGE0
        WORKER2 --> JUDGE0
        WORKER3 --> JUDGE0
    end

    %% --- Observability ---
    subgraph "Observability Stack"
        PROM["📈 Prometheus"]
        GRAFANA["📉 Grafana\n(pre-built dashboards)"]
        LOKI["📝 Loki\n(log aggregation)"]
        ALERTS["🔔 Alertmanager\n(PagerDuty / Slack)"]
    end

    %% --- Connections ---
    WEB     -->|"HTTPS / JWT"| TRAEFIK
    VSCODE  -->|"HTTPS / JWT"| TRAEFIK
    CDN     --> TRAEFIK
    TRAEFIK --> RATE
    RATE    --> CORS
    CORS    --> API

    API     -->|"enqueue job"| REDIS
    API     -->|"read/write"| PG
    API     -->|"WebSocket"| WEB

    REDIS   -->|"BLPOP dequeue"| WORKER1
    REDIS   -->|"BLPOP dequeue"| WORKER2
    REDIS   -->|"BLPOP dequeue"| WORKER3

    WORKER1 -->|"POST batch, poll"| JUDGE0
    WORKER2 -->|"POST batch, poll"| JUDGE0
    WORKER3 -->|"POST batch, poll"| JUDGE0

    JUDGE0  -->|"write results"| PG
    JUDGE0  -->|"ZINCRBY score"| REDIS
    JUDGE0  -->|"pubsub verdict"| REDIS
    REDIS   -->|"pubsub → WS push"| API

    PROM    --> GRAFANA
    LOKI    --> GRAFANA
    PROM    -->|"judge_queue_depth > 1000"| ALERTS
    PROM    -->|"judge0_down for 1m"| ALERTS

    style WEB fill:#3B82F6,stroke:#1D4ED8,color:#fff
    style VSCODE fill:#007ACC,stroke:#00509E,color:#fff
    style REDIS fill:#DC2626,stroke:#991B1B,color:#fff
    style PG fill:#336791,stroke:#1D4E8A,color:#fff
    style JUDGE0 fill:#F97316,stroke:#C2410C,color:#fff
    style TRAEFIK fill:#24C8EF,stroke:#0E7490,color:#fff
    style API fill:#10B981,stroke:#065F46,color:#fff
```

### Infrastructure Notes

- **Traefik** handles TLS termination, rate limiting, CORS headers, CSP, X-Frame-Options, and HSTS
- **FastAPI** runs behind gunicorn with 2 Uvicorn worker processes; each worker has its own async event loop
- **RQ Workers** run `--concurrency 4` (4 simultaneous jobs per process); multiple worker processes may be started for higher throughput
- **Judge0** runs as an isolated Docker container with `isolate` (the IOI sandbox), `runAsNonRoot`, `seccomp: RuntimeDefault`, and no network access

---

## 2. Data Flow Diagram — End-to-End Submission

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User<br/>(Web / VS Code)
    participant FE as ⚡ Frontend<br/>(Monaco Editor)
    participant API as 🚀 FastAPI API<br/>(/submissions/run)
    participant PG as 🐘 PostgreSQL<br/>(Submission row)
    participant RQ as 🟢 Redis Queue<br/>(algobattle:queue:judge)
    participant W as 👷 RQ Worker<br/>(judge orchestrator)
    participant J0 as �andbox Judge0<br/>(Docker + isolate)
    participant WS as 🔄 WebSocket<br/>(pubsub gateway)
    participant LB as 📊 Leaderboard<br/>(Redis ZSET)

    %% Step 1-2: User writes and submits code
    U->>+FE: Write code in Monaco editor
    FE->>U: Display editor
    U->>FE: Click "Run Tests" / "Submit"
    FE->>+API: POST /api/submissions/run<br/>{problem_id, language, code}

    %% Step 3-4: API persists and enqueues
    API->>+PG: INSERT Submission(status=PENDING)
    PG-->>-API: submission_id
    API->>+RQ: RPUSH algobattle:queue:judge<br/>{submission_id, mode: "run"}
    RQ-->>-API: OK (job enqueued)
    API-->>-FE: 202 Accepted<br/>{submission_id, status_url}

    %% Step 5: Frontend subscribes for live updates
    FE->>+WS: WebSocket /ws/submissions/{id}
    WS-->>FE: Connected

    %% Step 6: Worker picks up the job
    Note over W: Worker loop: BLPOP (blocking)
    W->>+RQ: BLPOP algobattle:queue:judge (blocks until job)
    RQ-->>-W: {submission_id, mode: "run"}
    W->>+PG: SELECT Submission + Problem<br/>+ visible TestCases
    PG-->>-W: code, language, testcases[]

    %% Step 7-8: Worker submits to Judge0 in batch
    W->>+J0: POST /submissions/batch?base64_encoded=true&wait=false<br/>[{code, lang, stdin} per testcase]
    J0-->>W: 200 OK + tokens[] (one per testcase)

    %% Step 9: Worker polls Judge0 until all done
    loop Poll until all tokens resolved
        W->>+J0: GET /submissions/{token}/batch
        J0-->>W: status: processing | completed | ...
    end

    %% Step 10: Worker maps results and writes to DB
    W->>+PG: UPDATE Submission(status=COMPLETED/FAILED)
    W->>+PG: INSERT SubmissionResult<br/>(per testcase: verdict, time_ms, memory_kb)
    PG-->>-W: OK

    %% Step 11: Contest leaderboard update (if AC)
    alt verdict == ACCEPTED && contest_id exists
        W->>+LB: ZINCRBY algobattle:contest:{id}:leaderboard<br/>+score user_id
        LB-->>-W: new_score
    end

    %% Step 12: Publish verdict via Redis pubsub
    W->>+WS: PUBLISH algobattle:pubsub:submission:{id}<br/>{verdict, time_ms, memory_kb, testcase_results[]}
    WS-->>-W: OK

    %% Step 13: WebSocket pushes to client
    WS->>FE: on_message: {verdict, ...}
    FE->>U: Display verdict banner<br/>+ update leaderboard

    Note over U: Verdict received in < 100ms of completion
```

---

## 3. Submission Lifecycle — State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: User submits code

    PENDING --> QUEUED: RQ RPUSH job<br/>to redis queue

    QUEUED --> RUNNING: Worker BLPOP<br/>grabs job from queue

    RUNNING --> COMPLETED: All testcases pass<br/>(verdict == ACCEPTED)
    
    RUNNING --> FAILED: One or more testcases fail<br/>(verdict != ACCEPTED)

    RUNNING --> JUDGE_ERROR: Judge0 returns 5xx<br/>or non-terminal status<br/>after 3 retries with backoff

    RUNNING --> TIMEOUT: Stuck in RUNNING > 60s<br/>(periodic checker detects)

    %% Terminal states
    COMPLETED --> [*]
    FAILED --> [*]
    JUDGE_ERROR --> [*]
    TIMEOUT --> QUEUED: Periodic checker<br/>re-enqueues the job

    %% Note on test mode vs submit mode
    note right of RUNNING
    TEST MODE: Per-testcase status (mix of AC/TLE/etc.)
    SUBMIT MODE: First-failure-wins → single verdict
    end note

    note right of QUEUED
    Queue: algobattle:queue:judge (Redis List)
    Job payload: {submission_id, mode: "run"|"submit"}
    end note

    note right of TIMEOUT
    Periodic checker runs every 30s,
    queries Submission where status=RUNNING
    and started_at < NOW() - 60s,
    then re-enqueues those jobs.
    end note
```

### Verdict Transitions Under RUNNING

```mermaid
stateDiagram-v2
    state RUNNING {
        [*] --> JUDGE0_POLLING: Worker POSTs batch<br/>to Judge0

        JUDGE0_POLLING --> AC: All testcases pass<br/>time_ms < limit, memory_kb < limit
        JUDGE0_POLLING --> TLE: RLIMIT_CPU exceeded<br/>or wall clock timeout
        JUDGE0_POLLING --> MLE: cgroup memory.max exceeded<br/>(memory bomb)
        JUDGE0_POLLING --> WA: Output mismatch<br/>(expected vs actual)
        JUDGE0_POLLING --> RTE: SIGSEGV, SIGABRT,<br/>SIGFPE, non-zero exit code
        JUDGE0_POLLING --> RE: Compile error,<br/>language not supported
        JUDGE0_POLLING --> CE: Runtime error<br/>(division by zero, etc.)
        JUDGE0_POLLING --> JUDGE_ERROR: HTTP 5xx from Judge0
        JUDGE0_POLLING --> SYSTEM_ERROR: Worker crash mid-judging

        AC --> [*]
        TLE --> [*]
        MLE --> [*]
        WA --> [*]
        RTE --> [*]
        RE --> [*]
        CE --> [*]
        JUDGE_ERROR --> [*]
        SYSTEM_ERROR --> [*]
    }
```

---

## 4. Security Model

### 4a. Sandboxing Layers

```mermaid
flowchart TB
    subgraph "Defense in Depth — Sandbox Layers"
        direction TB

        L1["🔒 Layer 1: RLIMIT_CPU\nCPU time limit per process\n• soft limit: problem time limit\n• hard limit: 2× time limit\n• SIGXCPU → TLE verdict"]

        L2["🔒 Layer 2: RLIMIT_FSIZE\nMax file size per process\n• limits output writing\n• prevents disk-filling attacks\n• SIGXFSZ → RTE verdict"]

        L3["🔒 Layer 3: Wall Clock Monitor\n(separate watchdog thread)\n• hard cap: time_limit × 2 + 5s\n• catches CPU + I/O loops\n• SIGKILL → TLE verdict"]

        L4["🔒 Layer 4: cgroup Memory Limits\ncgroup v2 memory.max\n• hard cap: problem memory limit\n• OOM killer → SIGKILL → MLE verdict"]

        L5["🔒 Layer 5: isolate (IOI Sandbox)\n• PIDs: max 64\n• fds: max 1024\n• no network (NET none)\n• tmpfs for /tmp (per-job)\n• read-only filesystem\n• no symlinks (CVE-2024-28185 patched)\n• seccomp: RuntimeDefault\n• caps: no CAP_SYS_ADMIN"]

        L6["🔒 Layer 6: Docker Container Isolation\n• non-root user (UID 65534)\n• read-only root filesystem\n• no-cap-add\n• tmpfs for /tmp\n• network: none\n• memory: problem limit + 50MB overhead"]

        L7["🔒 Layer 7: Judge0 Network Isolation\n• Judge0 container has no network\n• Worker connects via Docker socket\n• Filesystem: overlayfs (scratch)"]
    end

    L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L7

    style L1 fill:#DC2626,stroke:#991B1B,color:#fff
    style L2 fill:#EA580C,stroke:#9A3412,color:#fff
    style L3 fill:#D97706,stroke:#92400E,color:#fff
    style L4 fill:#CA8A04,stroke:#854D0E,color:#fff
    style L5 fill:#16A34A,stroke:#166534,color:#fff
    style L6 fill:#0D9488,stroke:#115E59,color:#fff
    style L7 fill:#4F46E5,stroke:#3730A3,color:#fff

    note over L1,L7: Each layer is independent —<br/>if one fails, the next catches it
```

### 4b. JWT Authentication Flow

```mermaid
sequenceDiagram
    participant BROWSER as 🌐 Browser<br/>(localStorage / JS)
    participant VSCODE as ⚡ VS Code<br/>(SecretStorage)
    participant API as 🚀 FastAPI API<br/>(/auth/*)
    participant PG as 🐘 PostgreSQL<br/>(users table)
    participant SECRET as 🔐 JWT Secret<br/>(rotating-secret env)

    %% Registration
    BROWSER->>+API: POST /auth/register<br/>{username, email, password}
    API->>+PG: INSERT INTO users<br/>(hashed with bcrypt)
    PG-->>-API: user_id
    API->>+SECRET: Sign JWT<br/>(sub=user_id, exp=7d)
    SECRET-->>-API: access_token
    API-->>-BROWSER: {access_token, user}

    %% Login
    BROWSER->>+API: POST /auth/login<br/>{email, password}
    API->>+PG: SELECT WHERE email
    PG-->>-API: user row + bcrypt_hash
    API->>API: bcrypt.verify(password, hash)
    API->>+SECRET: Sign JWT<br/>(sub=user_id, exp=7d)
    SECRET-->>-API: access_token
    API-->>-BROWSER: {access_token, user}

    %% Authenticated request
    BROWSER->>+API: GET /problems<br/>Authorization: Bearer <token>
    API->>+SECRET: Verify & decode JWT
    SECRET-->>-API: {sub: user_id, exp, ...}
    alt token valid & not expired
        API-->>-BROWSER: 200 {problems: [...]}
    else token expired
        API-->>-BROWSER: 401 Unauthorized<br/>{detail: "Token expired"}
    else token invalid
        API-->>-BROWSER: 401 Unauthorized<br/>{detail: "Invalid token"}
    end

    %% VS Code extension flow
    Note over VSCODE: algobattle.login command
    VSCODE->>+API: POST /auth/login<br/>{email, password}
    API-->>-VSCODE: {access_token}
    VSCODE->>VSCODE: Store in SecretStorage<br/>(macOS Keychain / Windows DPAPI / Linux libsecret)<br/>NOT localStorage
    Note over VSCODE: algobattle.runTests command
    VSCODE->>+API: POST /submissions/run<br/>Authorization: Bearer <token><br/>(fetched from SecretStorage)
    API-->>-VSCODE: 202 Accepted

    %% Secret rotation
    Note over SECRET: On container restart,<br/>rotating-secret refreshes JWT_SECRET env var
    SECRET->>API: New secret loaded
    Note over API: Old tokens remain valid<br/>until expiry (stateless JWT)
```

---

## 5. Determinism Guarantees

```mermaid
flowchart LR
    subgraph "Determinism Contract"
        direction TB
        
        INPUT["📥 Same Problem Input\n(problem_id + testcase set)"]
        CODE["📄 Same Submitted Code\n(exact bytes, language)"]
        ENV["🌍 Same Execution Environment\n(same Judge0 image, same limits)"]
        
        OUTPUT["📤 Same Execution Output\n(verdict, time_ms, memory_kb)"]
    end

    INPUT -->|problem_id| ENV
    CODE -->|language + source| ENV
    ENV --> OUTPUT

    subgraph "What Env Holds Constant"
        KERNEL["✅ Kernel version\n(pinned Docker image)"]
        JUDGE0_VERSION["✅ Judge0 version\n(pinned ≥ 1.13.2)"]
        LIBRARIES["✅ Language runtime versions\n(pinned base images)"]
        SEED["✅ PRNG seed: 0\n(no randomness in scoring)"]
        TIMING["✅ CPU quota: deterministic\n(cgroup CFS quota)"]
        NETWORK["✅ Network: completely blocked"]
        FILESYSTEM["✅ Read-only base + tmpfs\n(no hidden state files)"]
    end

    ENV --- KERNEL
    ENV --- JUDGE0_VERSION
    ENV --- LIBRARIES
    ENV --- SEED
    ENV --- TIMING
    ENV --- NETWORK
    ENV --- FILESYSTEM

    subgraph "Enforcement Mechanisms"
        SANDBOX["�andbox isolate\n(guarantees no side effects)"]
        CONTAINER["🐳 Docker image immutable\n(sha256 digest pinned)"]
        TESTCASE_HASH["🔒 Testcase input hashed\n(prevent tampering)"]
    end

    SANDBOX --> OUTPUT
    CONTAINER --> SANDBOX
    TESTCASE_HASH --> SANDBOX

    style INPUT fill:#3B82F6,stroke:#1D4ED8,color:#fff
    style CODE fill:#3B82F6,stroke:#1D4ED8,color:#fff
    style ENV fill:#10B981,stroke:#065F46,color:#fff
    style OUTPUT fill:#10B981,stroke:#065F46,color:#fff
    style SANDBOX fill:#F97316,stroke:#C2410C,color:#fff
    style CONTAINER fill:#F97316,stroke:#C2410C,color:#fff
```

### Scoring Determinism

```mermaid
flowchart LR
    A["Same AC submission"] --> B1["Test run 1\ntime_ms: 45ms"]
    A --> B2["Test run 2\ntime_ms: 43ms"]
    A --> B3["Test run 3\ntime_ms: 46ms"]

    B1 --> C["Min of all runs = 43ms"]
    B2 --> C
    B3 --> C

    C --> D["Score = max(0, 100 × (T - t) / T)\nwhere T = problem time limit"]
    D --> E["🏆 Leaderboard score"]

    Note over C,D: We take the BEST (minimum)<br/>execution time across runs,<br/>NOT the average, to reward<br/>consistent fast code
```

---

## 6. Contest Leaderboard Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant FE as ⚡ Frontend<br/>(Leaderboard component)
    participant API as 🚀 FastAPI<br/>(/contests/{id}/leaderboard)
    participant RQ as 🟢 Redis Queue
    participant W as 👷 RQ Worker
    participant J0 as �andbox Judge0
    participant LB as 📊 Redis ZSET<br/>(algobattle:contest:{id}:leaderboard)
    participant PG as 🐘 PostgreSQL
    participant WS as 🔄 WebSocket Gateway

    %% Submission
    U->>+FE: Submit solution to contest problem
    FE->>+API: POST /api/submissions/submit<br/>{contest_id, problem_id, code, language}
    API->>+PG: INSERT Submission(status=PENDING,<br/>contest_id, problem_id, user_id)
    PG-->>-API: submission_id
    API->>+RQ: RPUSH algobattle:queue:judge<br/>{submission_id, mode: "submit", contest_id}
    RQ-->>-API: OK
    API-->>-FE: 202 Accepted

    %% Judging
    W->>+RQ: BLPOP algobattle:queue:judge
    RQ-->>-W: job payload
    W->>+PG: SELECT submission + ALL testcases<br/>(including hidden)
    PG-->>-W: data
    W->>+J0: POST /submissions/batch<br/>(all testcases)
    J0-->>-W: results per testcase
    W->>W: Aggregate verdict (first-failure-wins)

    %% Score update
    alt verdict == ACCEPTED
        W->>+LB: ZSCAN contest leaderboard ZSET<br/>to get current score
        LB-->>-W: current_user_score
        W->>W: Calculate delta: problem_weight × (1 if first_AC else 0.1)
        W->>+LB: ZINCRBY algobattle:contest:{id}:leaderboard<br/>delta user_id
        LB-->>-W: new_total_score
        W->>W: Update rank: ZREVRANK
    end

    %% Persist
    W->>+PG: UPDATE Submission<br/>(status=COMPLETED, verdict, time_ms)
    W->>+PG: INSERT SubmissionResult<br/>(per testcase)
    PG-->>-W: OK

    %% Push live update
    W->>+WS: PUBLISH algobattle:pubsub:contest:{id}:leaderboard<br/>{user_id, new_score, new_rank, delta}
    WS-->>-W: OK

    %% Client receives live update
    WS->>+FE: WebSocket: on_leaderboard_update<br/>{rank, score, delta}
    FE->>FE: Sort and re-render leaderboard
    FE->>U: 🏆 Leaderboard updated in real-time

    %% Full leaderboard retrieval
    U->>+FE: Opens contest leaderboard
    FE->>+API: GET /api/contests/{id}/leaderboard<br/>?top=50
    API->>+LB: ZREVRANGE with scores<br/>(top 50)
    LB-->>-API: [(user_id, score), ...]
    API->>+PG: SELECT user details<br/>WHERE id IN (...)
    PG-->>-API: username, avatar_url
    API-->>-FE: [{rank, username, score, delta}, ...]
    FE->>U: Render leaderboard table

    Note over LB: ZSET score = total weighted AC score<br/>ZSET members = user_ids
    Note over LB: ZINCRBY is atomic — no race condition<br/>between simultaneous submissions
```

---

## 7. Database Schema — ER Diagram

```mermaid
erDiagram
    USER ||--o{ SUBMISSION : "submits"
    USER {
        uuid id PK
        string username UK
        string email UK
        string password_hash
        timestamp created_at
        timestamp updated_at
        boolean is_active
    }

    PROBLEM ||--o{ TESTCASE : "has"
    PROBLEM ||--o{ SUBMISSION : "receives"
    PROBLEM ||--o{ CONTEST_PROBLEM : "belongs to"
    PROBLEM {
        uuid id PK
        string slug UK
        string title
        text description
        string difficulty
        integer time_limit_ms
        integer memory_limit_kb
        jsonb input_schema
        jsonb output_schema
        jsonb solution_template
        boolean is_public
        timestamp created_at
        timestamp updated_at
    }

    TESTCASE ||--o{ SUBMISSION_RESULT : "validates"
    TESTCASE {
        uuid id PK
        uuid problem_id FK
        text stdin
        text expected_stdout
        text expected_stderr
        integer weight
        boolean is_sample
        boolean is_hidden
        integer time_limit_ms
        integer memory_limit_kb
        timestamp created_at
    }

    SUBMISSION ||--o| CONTEST_PARTICIPANT : "belongs to"
    SUBMISSION ||--o{ SUBMISSION_RESULT : "produces"
    SUBMISSION {
        uuid id PK
        uuid user_id FK
        uuid problem_id FK
        uuid contest_participant_id FK "nullable"
        string language
        text source_code
        string status
        string verdict
        integer total_time_ms
        integer total_memory_kb
        timestamp submitted_at
        timestamp judged_at
        string mode "run | submit"
    }

    SUBMISSION_RESULT {
        uuid id PK
        uuid submission_id FK
        uuid testcase_id FK
        string verdict
        integer time_ms
        integer memory_kb
        text stdout
        text stderr
        text compile_output
        timestamp created_at
    }

    CONTEST ||--o{ CONTEST_PARTICIPANT : "has"
    CONTEST ||--o{ CONTEST_PROBLEM : "contains"
    CONTEST {
        uuid id PK
        string slug UK
        string title
        text description
        timestamp starts_at
        timestamp ends_at
        string scoring_type "ICPC | ioi | custom"
        boolean is_public
        timestamp created_at
    }

    CONTEST_PARTICIPANT ||--o| USER : "represents"
    CONTEST_PARTICIPANT ||--o| CONTEST : "enrolled in"
    CONTEST_PARTICIPANT ||--o{ SUBMISSION : "submits"
    CONTEST_PARTICIPANT {
        uuid id PK
        uuid user_id FK
        uuid contest_id FK
        timestamp joined_at
        integer total_score
        integer rank
    }

    CONTEST_PROBLEM ||--o| PROBLEM : "references"
    CONTEST_PROBLEM ||--o| CONTEST : "belongs to"
    CONTEST_PROBLEM {
        uuid id PK
        uuid contest_id FK
        uuid problem_id FK
        integer order_index
        integer points
    }

    %% Index annotations
    note right of SUBMISSION::status
        Index: (problem_id, status)
        Index: (user_id, problem_id)
        Index: (contest_participant_id, submitted_at)
    end note

    note right of TESTCASE::stdin
        Index: (problem_id, is_hidden)
    end note

    note right of CONTEST_PARTICIPANT::rank
        Index: (contest_id, total_score DESC)
    end note
```

### Table Relationships Summary

```mermaid
flowchart LR
    USER["👤 USER\n(uuid, username, email)"]
    PROBLEM["📋 PROBLEM\n(uuid, slug, time_limit_ms)"]
    TESTCASE["🧪 TESTCASE\n(uuid, problem_id FK)"]
    SUBMISSION["📤 SUBMISSION\n(uuid, user_id, problem_id FK)"]
    RESULT["📊 SUBMISSION_RESULT\n(uuid, submission_id, testcase_id FK)"]
    CONTEST["🏆 CONTEST\n(uuid, slug, scoring_type)"]
    PARTICIPANT["👥 CONTEST_PARTICIPANT\n(uuid, user_id, contest_id FK)"]
    CONTEST_PROBLEM["🔗 CONTEST_PROBLEM\n(uuid, contest_id, problem_id FK)"]

    USER -->|"1:N"| SUBMISSION
    PROBLEM -->|"1:N"| TESTCASE
    PROBLEM -->|"1:N"| SUBMISSION
    SUBMISSION -->|"1:N"| RESULT
    TESTCASE -->|"1:N"| RESULT
    CONTEST -->|"1:N"| PARTICIPANT
    USER -->|"1:N"| PARTICIPANT
    CONTEST -->|"1:N"| CONTEST_PROBLEM
    PROBLEM -->|"1:N"| CONTEST_PROBLEM
    PARTICIPANT -->|"1:N"| SUBMISSION

    style USER fill:#3B82F6,stroke:#1D4ED8,color:#fff
    style PROBLEM fill:#10B981,stroke:#065F46,color:#fff
    style TESTCASE fill:#10B981,stroke:#065F46,color:#fff
    style SUBMISSION fill:#F97316,stroke:#C2410C,color:#fff
    style RESULT fill:#F97316,stroke:#C2410C,color:#fff
    style CONTEST fill:#8B5CF6,stroke:#6D28D9,color:#fff
    style PARTICIPANT fill:#8B5CF6,stroke:#6D28D9,color:#fff
    style CONTEST_PROBLEM fill:#EC4899,stroke:#BE185D,color:#fff
```

---

## 8. Disruption Handling

```mermaid
flowchart TB
    subgraph "Disruption Types"
        direction TB

        %% Row 1: Infinite loops
        DISRUPT1["♾️ Infinite Loop\n(while True: pass)"]
        DISRUPT2["📈 Memory Bomb\n(malloc until OOM)"]
        DISRUPT3["💥 Segmentation Fault\n(null pointer deref)"]
        DISRUPT4["🧮 Division by Zero\n(raise SIGFPE)"]
        DISRUPT5["⏱️ Wall Clock Timeout\n(10× time limit + overhead)"]
        DISRUPT6["🌐 Network Access Attempt\n(curl / socket.connect)"]
        DISRUPT7["📁 Filesystem Escape\n(symlink to /etc/passwd)"]
        DISRUPT8["💾 Disk Fill\n(write infinite bytes)"]
        DISRUPT9["🔧 Judge0 HTTP Error\n(500 / timeout / crash)"]
        DISRUPT10["👷 Worker Crash\n(kill -9 mid-judging)"]
    end

    %% Detection layer
    subgraph "Detection Mechanisms"
        DET1["⏱️ RLIMIT_CPU\nSIGXCPU after soft limit"]
        DET2["🔒 cgroup memory.max\nOOM killer → SIGKILL"]
        DET3["🛡️ isolate SIGSEGV\ncaught by sandbox"]
        DET4["🛡️ isolate SIGFPE\ncaught by sandbox"]
        DET5["🐕 Watchdog Thread\nseparate process, wall clock"]
        DET6["🌍 isolate NET none\nconnection refused"]
        DET7["🛡️ isolate --no-symlink\nCVE-2024-28185 patched\n(Judge0 ≥ 1.13.2)"]
        DET8["🔒 RLIMIT_FSIZE\nSIGXFSZ → RTE"]
        DET9["🔄 Retry 3× with backoff\nthen → JUDGE_ERROR"]
        DET10["🔄 Periodic checker\n(stuck > 60s → re-enqueue)"]
    end

    %% Verdict mapping
    subgraph "Verdict Output"
        V1["⏱️ TLE — Time Limit Exceeded"]
        V2["💾 MLE — Memory Limit Exceeded"]
        V3["💥 RTE — Runtime Error\n(SIGSEGV)"]
        V4["💥 RTE — Runtime Error\n(SIGFPE)"]
        V5["⏱️ TLE — Time Limit Exceeded\n(wall clock)"]
        V6["💥 RTE — Runtime Error\n(network I/O)"]
        V7["💥 RTE — Runtime Error\n(filesystem violation)"]
        V8["💥 RTE — Runtime Error\n(disk limit)"]
        V9["⚠️ JUDGE_ERROR — Judge system failure"]
        V10["⚠️ JUDGE_ERROR → re-enqueued\n→ eventually RUNNING → COMPLETED"]
    end

    %% Connections
    DISRUPT1 --> DET1
    DISRUPT1 --> DET5
    DET1 --> V1
    DET5 --> V1

    DISRUPT2 --> DET2
    DET2 --> V2

    DISRUPT3 --> DET3
    DET3 --> V3

    DISRUPT4 --> DET4
    DET4 --> V4

    DISRUPT5 --> DET5
    DET5 --> V5

    DISRUPT6 --> DET6
    DET6 --> V6

    DISRUPT7 --> DET7
    DET7 --> V7

    DISRUPT8 --> DET8
    DET8 --> V8

    DISRUPT9 --> DET9

    DISRUPT10 --> DET10
    DET10 --> V10

    %% Style
    style DISRUPT1 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT2 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT3 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT4 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT5 fill:#FEF3C7,stroke:#D97706,color:#78350F
    style DISRUPT6 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT7 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT8 fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style DISRUPT9 fill:#FEF3C7,stroke:#D97706,color:#78350F
    style DISRUPT10 fill:#FEF3C7,stroke:#D97706,color:#78350F

    style V1 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V2 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V3 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V4 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V5 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V6 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V7 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V8 fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style V9 fill:#FFEDD5,stroke:#EA580C,color:#7C2D12
    style V10 fill:#FFEDD5,stroke:#EA580C,color:#7C2D12
```

### Verdict Enum Reference

```mermaid
flowchart LR
    subgraph "VERDICT enum (11 values)"
        AC["✅ ACCEPTED\nAll testcases pass"]
        TLE["⏱️ TLE\nTime limit exceeded"]
        MLE["💾 MLE\nMemory limit exceeded"]
        WA["❌ WA\nWrong answer"]
        RTE["💥 RTE\nRuntime error"]
        CE["🔧 CE\nCompilation error"]
        RE["⚠️ RE\nRestricted function\n(network, filesystem)"]
        SE["🚨 SE\nSystem error\n(Judge0 / worker down)"]
        PE["📝 PE\nPresentation error\n(output format issues)"]
        SK["⏭️ SK\nSkipped\n(not judged)"]
        PEND["⏳ PENDING\nNot yet judged"]
    end

    AC -->|"= SUCCESS"| SUCCESS["🏆 Contest score +1"]
    TLE -->|"≠ SUCCESS"| FAIL
    MLE -->|"≠ SUCCESS"| FAIL
    WA -->|"≠ SUCCESS"| FAIL
    RTE -->|"≠ SUCCESS"| FAIL
    CE -->|"≠ SUCCESS"| FAIL
    RE -->|"≠ SUCCESS"| FAIL
    SE -->|"≠ SUCCESS"| FAIL
    PE -->|"≠ SUCCESS"| FAIL
    SK -->|"≠ SUCCESS"| FAIL
    PEND -->|"≠ SUCCESS"| FAIL

    style AC fill:#DCFCE7,stroke:#16A34A,color:#14532D
    style SUCCESS fill:#DCFCE7,stroke:#16A34A,color:#14532D
    style FAIL fill:#FEE2E2,stroke:#DC2626,color:#7F1D1D
    style TLE fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style MLE fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style WA fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style RTE fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style CE fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style RE fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style SE fill:#FFEDD5,stroke:#EA580C,color:#7C2D12
    style PE fill:#FEF9C3,stroke:#CA8A04,color:#713F12
    style SK fill:#F3F4F6,stroke:#6B7280,color:#374151
    style PEND fill:#F3F4F6,stroke:#6B7280,color:#374151
```

---

*Generated from `ARCHITECTURE.md` — all diagrams use Mermaid syntax and render in any Mermaid-compatible viewer (GitHub, GitLab, VS Code Mermaid Preview, mermaid.live).*
