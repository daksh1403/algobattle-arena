# leaderboard module

**Interface contract**

| Symbol | Purpose |
| --- | --- |
| `LeaderboardService` | Redis-backed ZSET operations |

**Redis keys**

| Key | Type | Score | Member |
| --- | --- | --- | --- |
| `contest:{id}:leaderboard` | ZSET | `total_points` (int) | `user_id` (str) |
| `contest:{id}:solve_times` | ZSET | `-solve_seconds` | `"{user_id}:{problem_id}"` |

**Why two ZSETs?**

The primary ZSET gives the public leaderboard (highest score first).  When
two users have identical scores, we tie-break by *aggregate solve time* —
reading from the secondary `solve_times` ZSET in Python.  This keeps the
hot-path reads simple (one ZREVRANGE) while still rewarding faster solves.

**Invariants**

- `add_participant` is idempotent (uses `ZADD NX`).
- `record_solve` writes are append-only — multiple writes for the same
  `(user_id, problem_id)` collapse via ZADD's overwrite semantics, which
  is the right behaviour: only the *first* solve should be recorded
  (the caller, `judge_submission`, enforces this).
