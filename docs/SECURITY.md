# Algobattle — Security Model

## Threat Model

The platform has two attack surfaces:
1. **Participants → API** (code injection, DDoS, auth bypass)
2. **Judge Worker → Host** (malicious code escaping the sandbox)

---

## 1. Authentication & Authorization

| Threat | Mitigation |
|---|---|
| Password brute-force | bcrypt with 12 rounds, failed-login lockout |
| JWT theft/replay | Short-lived tokens (30min), stored in httpOnly conceptually |
| Privilege escalation | `is_admin` flag in DB, `AdminUserId` dependency enforced on all admin routes |
| CSRF | FastAPI's stateless JWT — no session cookies |

**Implementation:** `app/modules/users/security.py` — bcrypt hashing, JWT encode/decode. `app/modules/deps.py` — `AdminUserId`, `get_current_user`.

---

## 2. API Rate Limiting

| Threat | Mitigation |
|---|---|
| Submission spam (burn judge quota) | slowapi — 30 submissions/min per IP |
| Login brute-force | 10 attempts/min per IP |
| Problem enumeration | Auth required for submissions |

**Implementation:** `slowapi` registered on `app/main.py`, applied to `POST /submissions/` at 30/min/IP.

---

## 3. Judge Sandbox (Defense-in-Depth)

The judge worker executes **untrusted participant code**. Seven layers of protection:

```
Layer 1: OS — RLIMIT_CPU (SIGXCPU after N seconds)
Layer 2: OS — RLIMIT_FSIZE (SIGXFSZ on excessive write)
Layer 3: Python — Wall-clock monitoring thread (SIGKILL if > N seconds)
Layer 4: Linux — cgroup memory.max (OOM kill at limit)
Layer 5: Linux — namespace isolation (PID, mount, network — no network access)
Layer 6: Docker — read-only container, no-cap, non-root user
Layer 7: Judge0 — seccomp-bpf allowlist (only safe syscalls)
```

### Linux Kernel (RLIMIT)

| Limit | Value | Enforcement |
|---|---|---|
| CPU time | 10s (Python), 5s (C) | SIGXCPU → `signal.SIGXCPU: "TLE"` |
| Output size | 128KB (configurable) | SIGXFSZ → `"OLE"` |
| Wall clock | 15s (Python), 10s (C) | Monitoring thread → `SIGKILL` → `"TLE"` |

**Implementation:** `backend/sandbox/sandbox_runner.py` — `_run_python()`, `_run_cpp()`

### cgroup / Namespace Isolation

| Setting | Value |
|---|---|
| Memory | 256MB per job (tmpfs) |
| CPU | Capped via cgroup CFS |
| Network | Dropped (no NET namespace) |
| PID | New PID namespace (hide host processes) |
| Mount | Read-only /usr, /lib, /lib64; /tmp as tmpfs |

**Implementation:** `infra/judge0/isolate.cfg` — Judge0's `isolate` configuration.

### Docker Container

```yaml
security_opt:
  - no-new-privileges:true
  - seccomp=builtin     # Allowlisted syscalls only
cap_drop: ALL
read_only: true         # Root filesystem read-only
user: judge             # Non-root user
```

**Implementation:** `infra/docker-compose.yml` — `judge-worker` service.

---

## 4. Known CVEs & Patches

| CVE | Severity | Affects | Fix |
|---|---|---|---|
| CVE-2024-28185 | CVSS 10.0 | Judge0 < 1.13.2 (symlink escape) | Pin `judge0/judge0:1.13.2` |
| CVE-2024-28189 | CVSS 9.8 | Judge0 < 1.13.2 (SSRF via language config) | Same as above |

**Mitigation:** `infra/judge0/docker-compose.judge0.yml` pins `image: judge0/judge0:1.13.2`.

---

## 5. WebSocket Security

| Threat | Mitigation |
|---|---|
| Connection hijacking | JWT validated on WS handshake (`ws_router.py`) |
| Mass subscription | Per-connection limit on topics |
| Subscription enumeration | Topic names are UUIDs (submission IDs), not guessable |

**Implementation:** `backend/app/ws_router.py` — validates JWT before WS upgrade.

---

## 6. Data Exposure

| Data | Exposure | Mitigation |
|---|---|---|
| Problem test cases | Hidden cases never sent to client | `visible=False` cases filtered in `ProblemService.get_visible_testcases()` |
| Leaderboard scores | Public | No PII, only username + score |
| JWT secret | `.env` | Never committed to git |

---

## 7. Input Validation

| Input | Validation |
|---|---|
| Code length | Max 64KB per submission |
| Language | Enum (`python`, `cpp`, `javascript`) |
| Problem slug | `^[a-z0-9-]+$` regex |
| Difficulty | Enum (`EASY`, `MEDIUM`, `HARD`) |
| Submission mode | Enum (`test`, `submit`) |

**Implementation:** Pydantic schemas in `app/modules/*/schemas.py` — validated before any DB write.

---

## 8. OWASP Top 10 Coverage

| OWASP Category | Coverage |
|---|---|
| A01 Broken Access Control | `AdminUserId`, JWT auth on all protected routes |
| A02 Cryptographic Failures | bcrypt(12), JWT RS256 |
| A03 Injection | Pydantic validation, no raw SQL |
| A04 Insecure Design | Rate limiting, sandboxing, modular architecture |
| A05 Security Misconfiguration | Docker defaults, seccomp, non-root containers |
| A06 Vulnerable Components | `pip audit`, `npm audit`, Trivy in CI |
| A07 Auth Failures | Failed-login tracking, JWT expiry |
| A08 Data Integrity | Deterministic judging, idempotent verdict writes |
| A09 Logging Failures | Prometheus metrics, structured logs |
| A10 SSRF | Judge0 network isolation, no outbound from worker |
