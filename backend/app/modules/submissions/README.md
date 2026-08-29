# submissions module

**Interface contract**

| Symbol | Purpose |
| --- | --- |
| `Submission` (model) | `user_id`, `problem_id`, `contest_id`, `language`, `code`, `status`, `runtime_ms`, `memory_kb`, `score`, `created_at`, `finished_at` |
| `SubmissionResult` (model) | per-testcase verdict: `status`, `runtime_ms`, `memory_kb`, `stdout`, `stderr`, `compile_output` |
| `SubmissionStatus` (enum) | `pending` → `running` → <terminal> |
| `SubmissionService` | `submit`, `get_by_id`, `get_results`, `list_for_user` |
| `JudgeClient` | async Judge0 client (`submit_batch`, `poll_batch`, `make_payload`) |
| `judge_submission` (RQ task) | grades one submission end-to-end |

**Pipeline**

```
client → POST /submissions
            │
            ▼
    SubmissionService.submit (PENDING row inserted)
            │
            ▼
    enqueue_judge_submission(submission_id)
            │
            ▼
   ┌──────────────────────────────┐
   │  RQ worker — judge_submission │
   │  1. Mark RUNNING              │
   │  2. POST batch to Judge0      │
   │  3. Poll until terminal       │
   │  4. Persist per-testcase rows │
   │  5. Update Submission row     │
   │  6. If AC + contest:          │
   │     - bump ContestParticipant │
   │     - ZADD leaderboard        │
   │     - record solve_time       │
   └──────────────────────────────┘
            │
            ▼
   client → GET /submissions/{id}  (polls until terminal)
```

**Determinism**

- Status transitions strictly `PENDING → RUNNING → terminal`.
- The RQ task is idempotent: if a submission is already terminal when the
  task starts, it returns early without re-running the judge.
- A submission with no test cases is marked `INTERNAL_ERROR` (deterministic
  fail rather than silently accepted).
