# contests module

**Interface contract**

| Symbol | Purpose |
| --- | --- |
| `Contest` | `name`, `start_at`, `end_at`, `is_active`, relations to participants + problems |
| `ContestParticipant` | (contest_id, user_id) UNIQUE, `total_points`, `joined_at` |
| `ContestProblem` | (contest_id, problem_id) UNIQUE, `position`, `score` |
| `ContestCreate` / `ContestOut` / `ContestSummary` / `ParticipantOut` / `ContestProblemOut` | schemas |
| `ContestService` | `create`, `get_by_id`, `list`, `join`, `list_participants`, `adjust_points` |
| `router` | `/contests` (GET, POST), `/contests/{id}` (GET), `/contests/{id}/join` (POST), `/contests/{id}/leaderboard` (GET), `/contests/{id}/participants` (GET) |

**Scoring rule**

ICPC-style: solving a problem grants the problem's `score`; **wrong submissions cost -20 each** (penalty applied by `app.modules.submissions.tasks.judge_submission` when a submission is graded).

**Invariants**

- `end_at > start_at` — enforced by pydantic schema validator.
- A user can join a contest only once — uniqueness constraint + `ConflictError`.
- `total_points` is updated transactionally by the submission worker; the leaderboard ZSET is updated alongside.
