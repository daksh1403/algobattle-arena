# Deterministic Judge Worker — Algobattle

## What This Is

A standalone Python worker that consumes submission jobs from a Redis queue and judges them with **deterministic, repeatable** behavior. It uses Judge0 (self-hosted) for sandboxed execution but wraps it with Algobattle-specific logic:

- **Deterministic ordering** — first-failure-wins (LeetCode style) or all-test-cases (debug mode) — chosen at submit time
- **Process preemption** — long-running submissions are killed by Judge0's wall-clock timer (`max-wall-time` in isolation.conf)
- **Memory overflow** — `max-memory` cgroup limit + `memory.max` triggers OOM-kill, reported as MLE
- **Infinite loops** — combination of `max-cpu-time` and `max-wall-time` guarantees termination. CPU time > wall time catches busy loops too.
- **Memory leaks** — OOM-kill catches unbounded allocation. We also bound heap per language via Judge0's `--stack-limit` / `cgmem`
- **Process crashes / segfaults / runtime errors** — captured in `stderr` and `compile_output` fields
- **Idempotent result writing** — if worker crashes mid-judging and a checker re-enqueues, we detect "already judged" via unique constraint on `(submission_id, testcase_id)` and skip

## Architecture

```
[API] -> [Redis Queue "judge"] -> [Worker]
                                          |
                                          v
                                    [Judge0 Client]
                                          |
                                          v
                                    [Judge0 /submissions/batch]
                                          |
                                          v
                                    [Poll /submissions/{token}/batch]
                                          |
                                          v
                                    [Status mapping]
                                          |
                                          v
                                    [DB write results + leaderboard update]
```

### Single Submission Flow

1. API enqueues `{"submission_id": int, "contest_id": int|null, "mode": "test"|"submit"}` to Redis list `algobattle:queue:judge`.
2. Worker pops the job. Sets status to `RUNNING` (writes DB row).
3. Fetch submission + problem + testcases (one query).
4. Build Judge0 batch payload — each testcase becomes one Judge0 sub-submission with stdin = base64(testcase.input), expected_output = base64(testcase.expected_output).
5. POST to Judge0.
6. Poll Judge0's batch endpoint (initial 0.5s, then 1s, 2s, capped at 30s total — exponential backoff).
7. Map each testcase result to a verdict:
   - `Accepted` → ACCEPTED
   - `Wrong Answer` → WRONG_ANSWER
   - `Time Limit Exceeded` → TLE
   - `Memory Limit Exceeded` → MLE
   - `Runtime Error` (any non-zero exit) → RUNTIME_ERROR
   - `Compile Error` → COMPILE_ERROR (stops all testcases, apply to all)
   - `Output Limit Exceeded` → OUTPUT_LIMIT_EXCEEDED
   - `status.id == 1|2` → still processing, keep polling
8. Aggregate verdict for the submission:
   - **test mode** → returns ARRAY of per-testcase results (no aggregation), individual test status shown
   - **submit mode** → first failure wins; set `submission.status = max(verdict_severity)`, `submission.runtime_ms = first_failure_runtime`, `submission.memory_kb = first_failure_memory`
9. If submission belongs to a contest AND verdict is ACCEPTED: update leaderboard ZSET (`algobattle:contest:{id}:leaderboard`) with `ZINCRBY key score_earned user_id`. Score is positive for correct solutions, negative per wrong submission (configurable, default -20 per wrong, ICPC-style).
10. Push update via WebSocket topic `contest:{id}:leaderboard` (pubsub channel `algobattle:pubsub:contest:{id}`).
11. Mark submission terminal.

### Resilience

- **Worker crash mid-job**: The DB row remains in `RUNNING` status. A periodic checker (cron job or APScheduler) finds `status = RUNNING` rows older than 60s and re-enqueues them. The CHECK constraint on `(submission_id, testcase_id)` ensures we don't double-count results.
- **Judge0 transient errors**: Worker retries the Judge0 call up to 3 times with exponential backoff (1s, 2s, 4s). After exhaustion: mark submission `JUDGE_ERROR` (a new status) and notify user.
- **Sandbox escapes**: impossible by design — Judge0 uses `isolate` with no network, no-write filesystem, cgroups, seccomp.

### Determinism Guarantee

- Each submission has a unique `submission_id` (UUID v4 stored as uuid column).
- Judge0 is stateless; each invocation is a fresh sandbox.
- We're not depending on `time.time()` for ranking — we use `score = -(accepted_time_seconds)` only AFTER the submission is marked ACCEPTED. Tiebreaker: lexicographic user_id (or submission_id).
- Testcases are sorted deterministically by `(is_sample DESC, ordinal ASC)` so a malicious user can't reorder.
- Compilation is deterministic per Judge0 versioning (pinned in isolation.conf).

## File Map (in `judge/`)

```
judge/
  worker.py              # main() — consume from queue, judge loop
  judge0_client.py       # httpx async client for Judge0 REST
  verdict_map.py         # Judge0 status.id -> our VERDICT enum + severity
  leaderboard.py         # Redis ZSET updates
  publisher.py           # WebSocket broadcast (via Redis pubsub)
  checker.py             # periodic task: re-enqueue stuck submissions
  tests/
    test_verdict_map.py
    test_leaderboard.py
    test_worker.py
    conftest.py
```

## Determinism test example

```python
# tests/test_worker.py
@pytest.mark.asyncio
async def test_same_submission_twice_produces_same_verdict():
    # submit identical code twice, must get identical status + runtime (within tolerance)
    ...

@pytest.mark.asyncio
async def test_first_failure_wins():
    # code that passes T1, fails T2, passes T3 -> final = WRONG_ANSWER (T2 result)
    ...

@pytest.mark.asyncio
async def test_infinite_loop_caught_as_tle():
    code = "while True: pass"
    # submit -> after 5s wall clock, judge returns TLE
    # submission.runtime_ms <= 5500 (5s timer + 0.5s slack)
    ...

@pytest.mark.asyncio
async def test_memory_bomb_caught_as_mle():
    code = "x = []\nwhile True: x.append('a' * 1024)"
    # submit -> judge returns MLE within 256MB limit
    ...
```

## Cost/Scale Math

- **Single worker** (4 concurrent jobs): ~120 submissions/min on a `t3.medium` (2 vCPU, 4GB) — Python stdlib in Judge0 image uses ~80MB per job.
- **10 workers** with `t3.large` dedicated: ~1200 sub/min — enough for 500 concurrent active users at typical contest load (~3 subs/user/min).
- Scale horizontally by adding RQ workers behind a single Redis queue. No code changes needed.

## Limitations / Future Work

- No interactive problems yet (only stdin/stdout batch judging).
- No plagiarism detection (MOSS / JPlag integration deferred to V2).
- No submission diff visualization (deferred).
- WebSocket broadcast currently via Redis pubsub → API gateway pushes to clients. At very high scale we'd switch to NATS or Kafka.
