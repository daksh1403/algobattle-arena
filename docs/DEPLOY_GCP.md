# Algobattle — Google Cloud (GCP) Deployment Guide

**Target audience:** Developers deploying Algobattle to Google Cloud using Cloud Run (serverless containers), Cloud SQL (managed PostgreSQL), and Cloud Memorystore (managed Redis). This guide covers a production-ready setup with HTTPS, no VMs to manage.

---

## Prerequisites

| Requirement | Details |
|---|---|
| GCP Project | `gcloud projects create algobattle --name="Algobattle"` |
| gcloud CLI | `brew install google-cloud-sdk` or `pip install gcloud` |
| Docker | For building images |
| Artifact Registry | Docker repository in GCP |
| Billing | Billing must be enabled on the project |
| APIs enabled | Cloud Run, Cloud SQL, Memorystore, Artifact Registry |

**Required IAM roles** for the deploying user:

```
roles/run.admin        # deploy Cloud Run services
roles/cloudsql.client  # connect to Cloud SQL
roles/cloudsql.instanceUser
roles/memorystore.redisEditor
roles/artifactregistry.writer
roles/iam.serviceAccountUser
```

---

## Step-by-Step Deployment

### 1. Set up environment and enable APIs

```bash
PROJECT_ID="your-algobattle-project"
REGION="us-central1"

gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com sqladmin.googleapis.com redis.googleapis.com artifactregistry.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create algobattle \
  --repository-format=docker \
  --location=$REGION \
  --description="Algobattle container images"
```

### 2. Build and push Docker images

```bash
cd algobattle

docker build -t ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/api:latest       ./backend
docker build -t ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/judge:latest      ./judge
docker build -t ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/frontend:latest    ./frontend

docker push ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/api:latest
docker push ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/judge:latest
docker push ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/frontend:latest
```

### 3. Create Cloud SQL (PostgreSQL 16)

```bash
# Managed PostgreSQL — handles backups, HA, patching automatically
gcloud sql instances create algobattle-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-size=20GB \
  --storage-type=SSD \
  --availability-type=ZONAL \
  --no-backup \
  --description="Algobattle primary database"

gcloud sql databases create algobattle --instance=algobattle-db

# Create app user (password set via Secret Manager below)
gcloud sql users create algobattle \
  --instance=algobattle-db \
  --password="CHANGE_ME_secure_password"
```

### 4. Create Cloud Memorystore (Redis 7)

```bash
gcloud redis instances create algobattle-redis \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=BASIC \
  --network=default

# Capture the Redis host for the next step
REDIS_HOST=$(gcloud redis instances describe algobattle-redis \
  --region=$REGION --format="value(host)")
echo "Redis host: $REDIS_HOST"
```

### 5. Create a service account for Cloud Run

```bash
SA_EMAIL="algobattle-run@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create algobattle-run \
  --display-name="Algobattle Cloud Run"

# Grant Cloud SQL access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudsql.client"
```

### 6. Deploy the API to Cloud Run

```bash
DB_HOST=$(gcloud sql instances describe algobattle-db \
  --format="value(ipAddresses[0].ipAddress)")
DB_PASS="CHANGE_ME_secure_password"  # replace with real value
SECRET_KEY=$(openssl rand -hex 32)

gcloud run deploy algobattle-api \
  --image=${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/api:latest \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8000 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=80 \
  --service-account=$SA_EMAIL \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://algobattle:${DB_PASS}@${DB_HOST}/algobattle" \
  --set-env-vars="REDIS_URL=redis://${REDIS_HOST}:6379/0" \
  --set-env-vars="SECRET_KEY=${SECRET_KEY}" \
  --set-env-vars="JWT_SECRET=${SECRET_KEY}" \
  --set-env-vars="APP_ENV=production" \
  --add-cloudsql-instances=${PROJECT_ID}:${REGION}:algobattle-db
```

### 7. Deploy the judge worker to Cloud Run (Background)

```bash
# Worker is a long-running job processor — no ingress, runs continuously
gcloud run deploy algobattle-worker \
  --image=${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/judge:latest \
  --platform=managed \
  --region=$REGION \
  --no-allow-unauthenticated \
  --memory=1Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=3 \
  --service-account=$SA_EMAIL \
  --command="python,-m,rq.worker,algobattle-judge" \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://algobattle:${DB_PASS}@${DB_HOST}/algobattle" \
  --set-env-vars="REDIS_URL=redis://${REDIS_HOST}:6379/0" \
  --set-env-vars="RQ_QUEUE_NAME=algobattle-judge" \
  --add-cloudsql-instances=${PROJECT_ID}:${REGION}:algobattle-db
```

### 8. Deploy the frontend as a static site on Cloud Run

```bash
# The frontend Dockerfile serves static files via nginx
gcloud run deploy algobattle-frontend \
  --image=${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/frontend:latest \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8080 \
  --memory=256Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5
```

### 9. Configure DNS and HTTPS

Cloud Run provides a managed HTTPS endpoint automatically. To use a custom domain:

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service=algobattle-frontend \
  --domain=contest.yoursite.com

# Get the DNS record to add (CNAME or A record)
# Follow GCP instructions to add it in your DNS provider
```

---

## Estimated Monthly Cost (dev tier, us-central1)

| Resource | Spec | Est. $/mo |
|---|---|---|
| Cloud Run — API | 0–2 instances, 512 Mi, 1 CPU | ~$5–40 (pay per use) |
| Cloud Run — Worker | 0–3 instances, 1 Gi, 2 CPU | ~$10–80 (pay per use) |
| Cloud Run — Frontend | 0–2 instances, 256 Mi | ~$2–20 (pay per use) |
| Cloud SQL PostgreSQL | db-f1-micro, 20 GB SSD | ~$25 |
| Memorystore Redis | 1 GB, Basic tier | ~$35 |
| Cloud Run egress | estimate | ~$5 |
| **Total** | | **~$82–165/mo** |

Cloud Run scales to zero when idle — dev with low traffic typically costs **$50–80/mo**.

---

## Verify the Deployment

```bash
API_URL=$(gcloud run services describe algobattle-api --region=$REGION \
  --format="value(status.url)")
FRONTEND_URL=$(gcloud run services describe algobattle-frontend --region=$REGION \
  --format="value(status.url)")

# Health check
curl $API_URL/health
# Expected: {"status":"ok","database":"ok","redis":"ok"}

# Smoke test
curl -X POST $API_URL/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"TestPass123!"}'
```

---

## Teardown (Avoid Lingering Resources)

```bash
# Delete Cloud Run services
gcloud run services delete algobattle-api --region=$REGION --quiet
gcloud run services delete algobattle-worker --region=$REGION --quiet
gcloud run services delete algobattle-frontend --region=$REGION --quiet

# Delete managed services
gcloud sql instances delete algobattle-db --quiet
gcloud redis instances delete algobattle-redis --region=$REGION --quiet

# Delete Artifact Registry repository
gcloud artifacts repositories delete algobattle --location=$REGION --quiet

# Verify nothing remains
gcloud run services list --region=$REGION
gcloud sql instances list
gcloud redis instances list --region=$REGION
```

---

## How to Modify and Customize

**Scale for a contest (thousands of concurrent users):**
```bash
# Auto-scale worker based on queue depth (use a Cloud Scheduler trigger or pub/sub)
gcloud run services update algobattle-worker \
  --region=$REGION \
  --max-instances=20 \
  --min-instances=1 \
  --concurrency=4

# Upgrade DB for contest
gcloud sql instances patch algobattle-db --tier=db-n1-standard-1 --quiet
```

**Switch to Cloud Run v2 (Anthos):** Replace `gcloud run deploy` with `gcloud run v2 services create` for GKE-based hosting with full Kubernetes control.

**Use Cloud Build for CI/CD:**
```yaml
# cloudbuild.yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args: [build, -t, ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/api:$COMMIT_SHA, ./backend]
  - name: gcr.io/cloud-builders/docker
    args: [push, ${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/api:$COMMIT_SHA]
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    args: [run, deploy, algobattle-api, --image=${REGION}-docker.pkg.dev/$PROJECT_ID/algobattle/api:$COMMIT_SHA, ...]
```

**Add Cloud Monitoring alerts:** GCP automatically scrapes Prometheus metrics if you expose `/metrics`. Create alerting policies in Cloud Console → Metrics → Alerting.
