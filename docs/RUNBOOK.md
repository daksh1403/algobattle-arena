# Algobattle — Operator Runbook

Common operational tasks and how to handle them.

## Health Checks

| Service | Endpoint | Healthy if |
|---|---|---|
| API | `GET /health` | 200 + `{"status": "ok"}` |
| API | `GET /readiness` | 200 + DB+Redis reachable |
| Judge0 | `GET /` | 200 |
| Worker | (no endpoint) | Prometheus queue_depth < 50 |
| Postgres | `pg_isready` | 0 |
| Redis | `redis-cli ping` | PONG |

## Common Tasks

### Bring the stack up (fresh)

```bash
cd algobattle/infra
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD, JWT_SECRET, etc.
make dev
make seed        # wait until API is up before seeding
make smoke       # confirms end-to-end works
```

### Restart a single service

```bash
docker compose restart api
docker compose restart judge-worker
```

### Inspect worker logs

```bash
make logs                                          # all
docker compose logs -f --tail=100 judge-worker    # just worker
```

### Re-seed problems

```bash
docker compose exec api python -m app.seed
```

### Manually submit a sample

```bash
curl -X POST http://localhost:8000/api/submissions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"problem_id": 1, "language": "python3", "code": "def solve(x): return x * 2"}'
```

### Promote a problem from PRIVATE test cases to PUBLIC

Edit directly in DB:

```sql
UPDATE test_cases SET is_public = TRUE WHERE problem_id = 1 AND is_sample = TRUE;
```

Or via admin CLI (work in progress).

### Force re-judge a submission

```bash
docker compose exec api python -m app.tasks.rejudge <submission_id>
```

### Stop queue processing temporarily

```bash
docker compose pause judge-worker
# Resume later:
docker compose unpause judge-worker
```

### Update Judge0 isolation config

1. Edit `infra/judge0/isolation.conf`.
2. `docker compose restart judge0`.
3. Verify: `curl http://localhost:2358/isolated`

## Alarms

### `judge_queue_depth > 1000` (15m)

1. Check worker logs: `docker compose logs judge-worker --tail=200`.
2. Most likely cause: one test problem has a memory-bomb test case.
3. Scale up: `docker compose up -d --scale judge-worker=4`.
4. If still rising: may be Judge0 itself failing. Check `curl http://localhost:2358/`.

### `api_p99_latency > 2s` (5m)

1. `docker compose stats` to identify resource exhaustion.
2. Likely cause: Redis connection pool. Restart API.
3. If persistent: increase `uvicorn --workers`.

### `postgres_disk > 80%`

1. Check `Submissions` size (often the biggest table): `SELECT pg_size_pretty(pg_total_relation_size('submissions'));`
2. Prune old test runs: `DELETE FROM submissions WHERE status NOT IN ('ACCEPTED') AND created_at < NOW() - INTERVAL '30 days';`
3. EBS volume resize: `aws ec2 modify-volume --volume-id vol-xxx --size 100`.

### `judge0_down` (1m)

1. `docker compose ps judge0`.
2. `docker compose logs judge0 --tail=200`. Common cause: out-of-memory or cgroup misconfig.
3. Restart: `docker compose restart judge0`.

## Disaster Recovery

### Postgres is lost

1. Restore from the most recent automated backup (RDS does this by default within 5 min).
2. After restore: re-seed any problems lost in the gap.
3. Verify leaderboard ZSETs (these are in Redis — separate failure domain). They can be rebuilt from `Submission` rows by running:
   ```bash
   docker compose exec api python -m app.tasks.rebuild_leaderboards
   ```

### Redis is lost

1. Leaderboards are GONE (Redis is ephemeral).
2. Run rebuild script (above).
3. In-flight queue jobs are GONE. Workers will mark stuck submissions as `JUDGE_ERROR` after timeout. Users can re-submit.

### Judge0 host lost

1. Spin up new host from infra Terraform.
2. Workers auto-reconnect to Judge0 at the new IP (update env var via your deploy pipeline).
3. Stuck submissions get re-enqueued by periodic checker.

### Whole stack loss

1. `terraform apply` from `infra/terraform/aws/`.
2. `helm install` (if on K8s) or `docker compose up -d`.
3. Restore DB from RDS snapshot.
4. Run rebuild scripts.

## Observability Quick Reference

### PromQL — submissions processed per minute

```
rate(submissions_total[1m]) * 60
```

### PromQL — average judge latency, p95

```
histogram_quantile(0.95, rate(judge_duration_seconds_bucket[5m]))
```

### PromQL — error rate (5xx)

```
sum(rate(api_requests_total{status_code=~"5.."}[5m]))
/
sum(rate(api_requests_total[5m]))
```

### PromQL — Judge0 queue depth

```
judge0_queue_size
```

### PromQL — Worker queue depth (Algobattle)

```
algobattle_judge_queue_depth
```

## Updating the Platform

1. Merge to main → CI runs.
2. After tests pass, push images via `make push`.
3. Deploy via `make deploy` (zero-downtime script) to single EC2, OR `helm upgrade algobattle ./infra/helm` for K8s.
4. Workers drain existing jobs before restart (drain timeout 30s).

## Security

### Rotate JWT secret

1. Update `JWT_SECRET` env var on API + workers.
2. Restart API and workers in same step (or staggered via load balancer).
3. All existing tokens become invalid; users re-login.

This is acceptable in production because JWTs have 24h expiry anyway — mass expiration is the cost of rotation.

### Patch a critical CVE in Judge0

1. Stop accepting new submissions: `docker compose pause judge-worker`.
2. Drain in-flight: wait for queue depth to reach 0, OR force `kill -TERM` (RQ worker finishes current job then exits).
3. `docker compose pull judge0` then `docker compose up -d judge0`.
4. Smoke test: `make smoke`.
5. Resume: `docker compose unpause judge-worker`.
