# Algobattle — Infrastructure

Production-grade DevOps infrastructure for the Algobattle competitive coding judge platform.

## What This Repo Provides

| Layer | Purpose | Tooling |
|-------|---------|---------|
| Local dev / single-host prod | Run everything on one machine | Docker Compose + Traefik |
| Production K8s | Scale judge workers horizontally | Helm chart |
| Production AWS | Cost-optimized single-AZ deployment | Terraform |
| Observability | Metrics, logs, dashboards, alerts | Prometheus + Grafana + Loki |
| CI/CD | Lint, test, build, push, deploy | GitHub Actions |

## Architecture

```
                   ┌──────────────────┐
                   │     Traefik      │  ← Let's Encrypt, rate limit
                   │   (reverse proxy)│
                   └─────────┬────────┘
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼────┐   ┌─────▼────┐   ┌─────▼────┐
        │ Frontend │   │   API    │   │ Grafana  │
        │ (Nginx)  │   │ (FastAPI)│   │  (UI)    │
        └──────────┘   └────┬─────┘   └──────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
           ┌────▼───┐  ┌────▼───┐  ┌────▼────┐
           │Postgres│  │ Redis  │  │ Judge   │
           │  (DB)  │  │ (queue)│  │ Workers │
           └────────┘  └───┬────┘  └────┬────┘
                           │            │
                           └──────┬─────┘
                                  │ HTTP
                            ┌─────▼─────┐
                            │  Judge0   │  (isolated subnet, own host in prod)
                            │  cluster  │
                            └───────────┘

Monitoring side-car:
  node-exporter → Prometheus → Grafana (LGTM)
                                  ↑
                              Loki ← Promtail
```

## Cost Targets (baseline, idle)

| Resource | Spec | Monthly USD |
|-----------|------|-------------|
| API + worker EC2 | t3.medium | ~$30 |
| Judge0 EC2 | t3.large | ~$60 |
| RDS postgres | db.t4g.micro | ~$15 |
| ALB | — | ~$20 |
| EBS gp3 (50 GB total) | — | ~$4 |
| Domain + Route 53 | — | ~$2 |
| **Total baseline** | — | **~$131 / mo** |

Scales to near-zero when idle (t3 burstable credits + RDS pause-on-idle not enabled by default, but achievable).

## Quick Start

```bash
cp .env.example .env
# Edit .env — at minimum set POSTGRES_PASSWORD and REDIS_PASSWORD
make dev           # bring up the full stack locally
make seed          # load sample problems
make smoke         # verify health + submit a sample
```

Open:
- App:        http://localhost
- API:        http://localhost/api
- Grafana:    http://localhost:3000  (admin / $GRAFANA_ADMIN_PASSWORD)
- Prometheus: http://localhost:9090

## Repo Layout

```
.
├── docker-compose.yml            # full production stack
├── docker-compose.dev.yml        # dev overrides
├── .env.example                  # every env var, documented
├── Makefile                      # dev / prod / test / deploy
│
├── api/                          # backend image
├── judge/                        # worker image
├── judge0/                       # Judge0 stack (isolated compose)
├── proxy/                        # Traefik config
├── monitoring/                   # Prometheus / Grafana / Loki
│
├── helm/                         # Kubernetes chart
├── terraform/                    # AWS IaC
│
├── scripts/                      # dev-up, smoke-test, seed, load-test
└── .github/workflows/            # CI, CD, security
```

## Deployment Options

### 1. Local / single-host (Docker Compose)
Cheapest. One VM, everything together. Good up to a few hundred concurrent users.

```bash
make prod
```

### 2. Kubernetes
Use the Helm chart. Judge0 stays on a dedicated node pool with privileged pods (for cgroup isolation).

```bash
helm install algobattle ./helm -n algobattle --create-namespace
```

### 3. AWS (Terraform)
Provision single-AZ infra: ALB + 2 EC2s + RDS. Cost-optimized.

```bash
cd terraform/aws
terraform init
terraform apply -var-file=environments/dev.tfvars
```

## Operational Notes

- **Judge0 requires privileged mode** to manage per-submission cgroups. We mitigate with a custom seccomp profile (see `helm/templates/judge0-deployment.yaml`).
- **Worker queue** is Redis (RQ). Scale workers horizontally via `make scale N=10` or via HPA in K8s.
- **Database backups** — RDS automated backups enabled; `pg_dump` snapshots on Sunday for local compose.
- **TLS** — Traefik auto-provisions Let's Encrypt certs in prod. Cert-manager does the same in K8s.
- **Secrets** — never committed. Use `.env` locally, AWS Secrets Manager in Terraform, K8s Secrets + External Secrets Operator in Helm.

## Upgrade Path

| Traffic | Recommended |
|---------|-------------|
| 0 – 500 concurrent users | Single EC2 (this repo) |
| 500 – 5 000 | Split API + workers into ASG; add Redis cluster |
| 5 000 – 50 000 | EKS / GKE, RDS Aurora, Judge0 on dedicated node pool |
| 50 000+ | Multi-region, queue sharding, Judge0 per-language pools |

## License

Internal. Algobattle platform — all rights reserved.