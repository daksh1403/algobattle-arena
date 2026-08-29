# Cost & Scaling Reference

Cost-effective choices are baked into the platform. This document shows the math.

## Local Dev

```bash
make dev
```

Cost: **$0** (your laptop).
Resources used: ~2 GB RAM, 1 vCPU burst. Suitable for problem drafting + testing, not for production traffic.

## Single-Host Cloud (Small)

For ≤50 concurrent users and ~600 submissions/min peak.

| Service | Spec | Monthly cost |
|---|---|---|
| EC2 t3.medium | 2 vCPU, 4 GB | ~$30 |
| RDS db.t4g.micro postgres | 2 GB RAM, 20 GB SSD | ~$15 |
| EBS gp3 50 GB | | ~$4 |
| Data transfer | minimal | ~$2 |
| **Total** | | **~$51 /mo** |

Run as single compose stack with Traefik. Postgres on RDS for backups.

## Multi-Host Cloud (Medium — Recommended Baseline)

For ≤500 concurrent users. Submissions peak ~3,500 /min during contests.

| Service | Spec | Monthly cost |
|---|---|---|
| EC2 t3.medium (API + worker) | 2 vCPU, 4 GB | ~$30 |
| EC2 t3.large dedicated (Judge0) | 2 vCPU, 8 GB | ~$60 |
| RDS db.t4g.small postgres | 2 GB RAM, 50 GB SSD | ~$30 |
| ALB | | ~$20 |
| S3 (test cases, frontend assets) | | ~$2 |
| CloudWatch (basic metrics) | | ~$3 |
| Data transfer | | ~$5 |
| **Total** | | **~$150 /mo** |

Judge0 lives on its own host for isolation (its cgroup config can't accidentally affect the API).

## Multi-AZ Kubernetes (Large — V2 path)

For ≤5,000 concurrent users. Do not migrate until you're at scale.

| Service | Spec | Monthly cost |
|---|---|---|
| EKS control plane | | ~$73 |
| EKS node group (judge workers, autoscaling 3–10) | 3× t3.large spot | ~$120 |
| EKS node group (api workers, autoscaling 2–6) | 2× t3.medium | ~$60 |
| RDS postgres multi-AZ db.t4g.medium | | ~$110 |
| ALB | | ~$25 |
| EFS (shared nothing, replicated via postgres) | | ~$30 |
| S3 + CloudFront CDN | | ~$15 |
| Route 53 | | ~$5 |
| CloudWatch + Grafana Cloud (logs) | | ~$50 |
| Data transfer | | ~$25 |
| **Total** | | **~$513 /mo** |

## Optimization Choices

### 1. Spot instances for stateless workers

Judge workers (RQ) are stateless — they pull from queue, run, and exit. Perfect for EC2 Spot (60–70% discount). On interruption: AWS gives 2-min warning, RQ worker drains current job and exits. The next pull from queue on another instance picks up where it left off. Set up a small on-demand "anchor" worker that picks up orphaned jobs.

### 2. Idle scale-down

Set up an EventBridge rule to stop the judge EC2 at night (or when queue is empty for 30 min). Costs drop to RDS + ALB + minimal data transfer (~$50/mo) during idle.

### 3. Self-host Judge0

Sphere Engine charges $0.30 /submission (or monthly plans). At 100k submissions/mo, that's $30k/year. Self-hosting Judge0 is **free** (open-source) and runs on the same hardware as our app.

### 4. Free observability tier

Use Grafana Cloud's free tier (10k metrics, 50 GB logs, 14-day retention) instead of running Prometheus + Grafana in EKS. Cuts the Large tier by ~$80/mo.

### 5. Single-AZ for non-prod

Dev/staging EKS clusters don't need multi-AZ. Save on data transfer and cross-AZ postgres replication. Multi-AZ only in production.

## Capacity Planning Math

```
Concurrent users  → submissions/min @ 3/min/user → workers needed
─────────────────────────────────────────────────────────────────
       10                    30                       1
      100                   300                       3
      500                  1500                      10
     5000                 15000                      50
```

Each worker process (RQ with concurrency=4) handles ~30 sub/min steady-state. Single machine can run 2 worker processes → ~60 sub/min. For 100 concurrent users (300 sub/min) you need 5 worker processes → 3 EC2 instances.

## When to Migrate

| Signal | Action |
|---|---|
| Sustained queue >100 | +1 worker process |
| API p99 >1s | +1 api uvicorn worker |
| Postgres connection pool exhausted (>80% of `max_connections=100`) | Upgrade RDS tier or move to read replicas |
| Judge0 latency high | Dedicated host, scale vertically |
| Multiple AZ required for HA | Migrate to EKS |

The Terraform module under `infra/terraform/aws/` ships with `dev.tfvars` (single t3.medium + db.t4g.micro) and `prod.tfvars` (multi-host, recommended baseline). Adjust `instance_type` and `count` per env.
