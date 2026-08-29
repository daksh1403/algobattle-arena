# problems module

**Interface contract**

| Symbol | Purpose |
| --- | --- |
| `Problem` (model) | `slug` (unique), `title`, `statement_md`, `difficulty`, `tags[]`, `time_limit_ms`, `memory_limit_kb`, `boilerplate_code` (JSON dict), `function_signature`, `solution_visibility`, `created_at` |
| `TestCase` (model) | `problem_id`, `input` (TEXT, JSON args), `expected_output`, `is_sample`, `is_public` |
| `Difficulty` enum | `easy` / `medium` / `hard` |
| `SolutionVisibility` enum | `public` / `private` |
| `ProblemCreate` / `ProblemUpdate` / `ProblemOut` / `ProblemSummary` | schemas |
| `ProblemService` | `create`, `get_by_id`, `get_by_slug`, `list(...)`, `list_test_cases(...)`, `update` |
| `router` | `/problems` (GET/POST), `/problems/{slug}` (GET), `/problems/{slug}/testcases` (GET) |

**Conventions**

- `tags` is `ARRAY(String(32))` on Postgres, `JSON` on SQLite (tests).
- `boilerplate_code` is `JSONB` on Postgres, `JSON` on SQLite.
- Test cases with `is_sample=True` are the ones users see before submitting; `is_public=True` ones are used for judging (private ones could be added later for plagiarism prevention).
