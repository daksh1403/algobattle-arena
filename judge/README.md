# Judge Worker

The deterministic judge worker lives in the backend module:

- **`../backend/app/modules/submissions/tasks.py`** — the RQ job entrypoint (`judge_submission`), the async judging pipeline (`_judge_async`), verdict aggregation, ICPC-style scoring, and leaderboard side-effects.
- **`../backend/app/modules/submissions/judge_client.py`** — the Judge0 REST client (submit batch, poll, status mapping, base64 handling).
- **`DETERMINISTIC_JUDGE.md`** — full design doc: determinism guarantees, disruption handling (infinite loops → TLE, OOM → MLE, preemption, worker crash recovery), cost math, and the resilience model.

The worker runs as a separate RQ process (see `../infra/docker-compose.yml` service `judge-worker`). It consumes jobs from Redis queue `algobattle-judge` and talks to Judge0 over HTTP.

Unit + integration tests for the worker live in `../backend/app/modules/submissions/tests/`.
