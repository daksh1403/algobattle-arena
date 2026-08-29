# Algobattle — Microsoft Azure Deployment Guide

**Target audience:** Teams deploying to Microsoft Azure using Azure Container Apps (serverless containers), Azure Database for PostgreSQL, and Azure Cache for Redis. No VMs to provision — fully managed, auto-scales with load.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Azure Subscription | With Owner or Contributor role |
| Azure CLI | `brew install azure-cli` or `winget install AzureCLI` |
| Docker | For building images |
| Azure Container Registry | Docker image storage |
| Resource group | `az group create --name algobattle-rg --location eastus` |

**Required RBAC roles** for the deploying user:

```
Contributor on the resource group
AcrPull / AcrPush on the container registry
```

---

## Step-by-Step Deployment

### 1. Log in and set defaults

```bash
az login
az config set defaults.location=eastus defaults.group=algobattle-rg

RESOURCE_GROUP="algobattle-rg"
LOCATION="eastus"
REGISTRY="algobattleregistry"

# Create resource group and registry
az group create --name $RESOURCE_GROUP --location $LOCATION
az acr create --resource-group $RESOURCE_GROUP --name $REGISTRY \
  --sku Basic --admin-enabled true

# Get registry credentials
ACR_LOGIN=$(az acr show --name $REGISTRY --query loginServer --output tsv)
ACR_PASSWORD=$(az acr credential show --name $REGISTRY \
  --query passwords[0].value --output tsv)
```

### 2. Build and push Docker images

```bash
cd algobattle

docker build -t ${ACR_LOGIN}/api:latest       ./backend
docker build -t ${ACR_LOGIN}/judge:latest     ./judge
docker build -t ${ACR_LOGIN}/frontend:latest  ./frontend

docker login --username=algobattleregistry --password=$ACR_PASSWORD $ACR_LOGIN
docker push ${ACR_LOGIN}/api:latest
docker push ${ACR_LOGIN}/judge:latest
docker push ${ACR_LOGIN}/frontend:latest
```

### 3. Create Azure Database for PostgreSQL

```bash
# Flexible Server — production-grade managed Postgres
DB_NAME="algobattle-db"
DB_ADMIN="algobattle_admin"
DB_PASS="ChangeMe123!"

az postgres flexible-server create \
  --name $DB_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku-name Standard_B1ms \
  --storage-size 20480 \
  --version 16 \
  --admin-user $DB_ADMIN \
  --admin-password $DB_PASS \
  --public-access none \
  --high-availability Disabled \
  --backup-retention 7

# Create the database
az postgres flexible-server db create \
  --resource-group $RESOURCE_GROUP \
  --server-name $DB_NAME \
  --database-name algobattle
```

### 4. Create Azure Cache for Redis

```bash
REDIS_NAME="algobattle-redis"

az redis create \
  --name $REDIS_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Basic \
  --vm-size c0 \
  --enable-non-ssl-port false

REDIS_HOST=$(az redis show --name $REDIS_NAME \
  --resource-group $RESOURCE_GROUP \
  --query hostName --output tsv)
REDIS_KEY=$(az redis list-keys --name $REDIS_NAME \
  --resource-group $RESOURCE_GROUP \
  --query primaryKey --output tsv)
```

### 5. Create Container Apps environment

```bash
ENV_NAME="algobattle-env"

az containerapp env create \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

### 6. Deploy the API

```bash
SECRET_KEY=$(openssl rand -hex 32)
DB_HOST=$(az postgres flexible-server show --name $DB_NAME \
  --resource-group $RESOURCE_GROUP \
  --query fullyQualifiedDomainName --output tsv)

az containerapp create \
  --name algobattle-api \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image ${ACR_LOGIN}/api:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 5 \
  --cpu 1.0 \
  --memory 1Gi \
  --env-vars "DATABASE_URL=postgresql+asyncpg://${DB_ADMIN}:${DB_PASS}@${DB_HOST}/algobattle" \
  --env-vars "REDIS_URL=redis://:${REDIS_KEY}@${REDIS_HOST}:6380/0" \
  --env-vars "SECRET_KEY=${SECRET_KEY}" \
  --env-vars "JWT_SECRET=${SECRET_KEY}" \
  --env-vars "APP_ENV=production" \
  --registry-server $ACR_LOGIN \
  --registry-username $REGISTRY \
  --registry-password $ACR_PASSWORD

# Wait for health
az containerapp show --name algobattle-api \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn
```

### 7. Deploy the judge worker

```bash
JUDGE_CALLBACK_URL=$(az containerapp show --name algobattle-api \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn --output tsv)

az containerapp create \
  --name algobattle-worker \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image ${ACR_LOGIN}/judge:latest \
  --cpu 2.0 \
  --memory 2Gi \
  --min-replicas 0 \
  --max-replicas 10 \
  --command python \
  --args "-m,rq.worker,algobattle-judge" \
  --env-vars "DATABASE_URL=postgresql+asyncpg://${DB_ADMIN}:${DB_PASS}@${DB_HOST}/algobattle" \
  --env-vars "REDIS_URL=redis://:${REDIS_KEY}@${REDIS_HOST}:6380/0" \
  --env-vars "RQ_QUEUE_NAME=algobattle-judge" \
  --env-vars "JUDGE_CALLBACK_URL=https://${JUDGE_CALLBACK_URL}" \
  --env-vars "JUDGE0_URL=https://${JUDGE_CALLBACK_URL}/judge0" \
  --registry-server $ACR_LOGIN \
  --registry-username $REGISTRY \
  --registry-password $ACR_PASSWORD

# Scale to at least 1 so it processes the queue
az containerapp update --name algobattle-worker \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 1
```

### 8. Deploy the frontend

```bash
# The frontend is a static React app served by nginx
az containerapp create \
  --name algobattle-frontend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image ${ACR_LOGIN}/frontend:latest \
  --target-port 8080 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 5 \
  --cpu 0.5 \
  --memory 512Mi \
  --env-vars "NEXT_PUBLIC_API_BASE=https://${JUDGE_CALLBACK_URL}/api" \
  --registry-server $ACR_LOGIN \
  --registry-username $REGISTRY \
  --registry-password $ACR_PASSWORD
```

### 9. Configure a custom domain (optional)

```bash
FRONTEND_FQDN=$(az containerapp show --name algobattle-frontend \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn --output tsv)

az containerapp hostname add \
  --resource-group $RESOURCE_GROUP \
  --app algobattle-frontend \
  --hostname contest.yoursite.com

# Add TXT record shown in Azure portal → Container Apps → Frontend → Ingress
# Then add CNAME: contest.yoursite.com → $FRONTEND_FQDN
```

---

## Estimated Monthly Cost (dev tier, East US)

| Resource | Spec | Est. $/mo |
|---|---|---|
| Azure Container Apps — API | 0–5 replicas, B1 (1 CPU, 1 Gi) | ~$10–50 (pay per use) |
| Azure Container Apps — Worker | 1–10 replicas, B2 (2 CPU, 2 Gi) | ~$20–100 (pay per use) |
| Azure Container Apps — Frontend | 0–5 replicas, B1 (0.5 CPU, 0.5 Gi) | ~$5–25 (pay per use) |
| Azure Database PostgreSQL | Flexible Server B1ms, 20 GB | ~$50 |
| Azure Cache Redis | Basic C0 (250 MB) | ~$25 |
| Log Analytics | pay-per-GB | ~$5 |
| **Total** | | **~$115–235/mo** |

Idle dev environment with Container Apps scale-to-zero typically runs **$80–120/mo**.

---

## Verify the Deployment

```bash
API_URL=$(az containerapp show --name algobattle-api \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn --output tsv)

# Health check
curl https://${API_URL}/health
# Expected: {"status":"ok","database":"ok","redis":"ok"}

# Register a test user
curl -X POST https://${API_URL}/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@test.com","password":"AdminPass123!"}'

# Check worker logs
az containerapp logs show --name algobattle-worker \
  --resource-group $RESOURCE_GROUP --tail=50
```

---

## Teardown (Avoid Lingering Resources)

```bash
# Delete all Container Apps
az containerapp delete --name algobattle-api --resource-group $RESOURCE_GROUP --yes
az containerapp delete --name algobattle-worker --resource-group $RESOURCE_GROUP --yes
az containerapp delete --name algobattle-frontend --resource-group $RESOURCE_GROUP --yes

# Delete Container Apps environment
az containerapp env delete --name $ENV_NAME --resource-group $RESOURCE_GROUP --yes

# Delete managed services
az postgres flexible-server delete --name $DB_NAME \
  --resource-group $RESOURCE_GROUP --yes
az redis delete --name $REDIS_NAME --resource-group $RESOURCE_GROUP --yes

# Delete container registry
az acr delete --name $REGISTRY --resource-group $RESOURCE_GROUP --yes

# Delete resource group (removes everything)
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

---

## How to Modify and Customize

**Scale worker for a contest:**
```bash
az containerapp update --name algobattle-worker \
  --resource-group $RESOURCE_GROUP \
  --max-replicas 20 \
  --cpu 2 \
  --memory 2Gi
```

**Upgrade PostgreSQL for prod:**
```bash
az postgres flexible-server update --name $DB_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku-name Standard_D2s_v3 \
  --tier GeneralPurpose
```

**Add a custom Judge0 deployment (Azure VM or Container Instances):**
```bash
# Judge0 needs isolated execution — use Azure Container Instances with no public IP
# then expose via internal network to the worker
az container create \
  --name algobattle-judge0 \
  --resource-group $RESOURCE_GROUP \
  --image judge0/judge0:latest \
  --cpu 2 \
  --memory 4Gi \
  --vnet algobattle-vnet \
  --subnet judge0-subnet \
  --secure-environment-variables "JUDGE0_LANGUAGE_IDS=74,71,50"
```

**CI/CD with Azure Pipelines:**
```yaml
# azure-pipelines.yml
- task: AzureCLI@2
  inputs:
    azureSubscription: 'Azure-Service-Connection'
    scriptType: 'bash'
    inlineScript: |
      az containerapp update \
        --name algobattle-api \
        --resource-group algobattle-rg \
        --image ${ACR_LOGIN}/api:$(Build.BuildId)
```

**Switch to Azure App Service (Web App):** Replace `az containerapp create` with `az webapp create --runtime PYTHON:3.11` and deploy via a zip file instead of Docker. This works for the API but not the judge worker (needs persistent process + full Redis access).
