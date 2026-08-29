# Algobattle — AWS Deployment Guide

**Target audience:** DevOps engineers or developers who need a production-ready, self-hosted deployment on AWS. This guide deploys the full stack: FastAPI API, React frontend, RQ judge worker, PostgreSQL (RDS), Redis (ElastiCache), and Judge0 on EC2, behind an Application Load Balancer.

---

## Prerequisites

| Requirement | Details |
|---|---|
| AWS Account | With programmatic access (access key + secret) |
| AWS CLI | `aws configure` or environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Terraform | ≥ 1.6 — `terraform install` or `brew install terraform` |
| Docker | For building and pushing images |
| EC2 Key Pair | Create `algobattle-prod` in the target region (AWS Console → EC2 → Key Pairs) |
| GitHub Container Registry | GHCR packages enabled; token with `read:packages` scope |

**IAM minimum permissions** for the deploying user:

```
ec2:RunInstances, ec2:Describe*, ec2:CreateKeyPair, ec2:DeleteKeyPair,
rds:Create*, rds:Describe*, rds:Delete*,
elasticloadbalancing:*, iam:*, secretsmanager:*, acm:*, cloudwatch:*
```

---

## Step-by-Step Deployment

### 1. Clone and navigate

```bash
git clone https://github.com/your-org/algobattle.git
cd algobattle/infra/terraform/aws
```

### 2. Configure environment variables

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export TF_VAR_github_org="your-org"
export TF_VAR_image_api="ghcr.io/your-org/algobattle-api:latest"
export TF_VAR_image_judge="ghcr.io/your-org/algobattle-judge:latest"
export TF_VAR_image_frontend="ghcr.io/your-org/algobattle-frontend:latest"
```

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Review and adjust variables

```bash
# Edit environments/dev.tfvars — update image refs after your first CI push
# For prod, use environments/prod.tfvars and set a real domain + certificate
cat environments/dev.tfvars
```

Key variables to change:

```
image_api      = "ghcr.io/your-org/algobattle-api:latest"
image_judge    = "ghcr.io/your-org/algobattle-judge:latest"
image_frontend = "ghcr.io/your-org/algobattle-frontend:latest"
ssh_key_name   = "algobattle-prod"   # must exist in your AWS account
domain_name    = "algobattle.example.com"  # optional — enables HTTPS
```

### 5. Plan and apply

```bash
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

Type `yes` when prompted. Terraform will output:

```
api_host        = "ec2-12-34-56-78.compute-1.amazonaws.com"
judge0_host     = "ec2-98-76-54-32.compute-1.amazonaws.com"
rds_endpoint    = "algobattle.xYZ.us-east-1.rds.amazonaws.com:5432"
ssh_command_api = "ssh -i ~/.ssh/algobattle-prod.pem ubuntu@ec2-..."
```

### 6. Build and push container images

```bash
# From infra/ directory
cd ../..

docker build -t ghcr.io/your-org/algobattle-api:latest       ./backend
docker build -t ghcr.io/your-org/algobattle-judge:latest     ./judge
docker build -t ghcr.io/your-org/algobattle-frontend:latest   ./frontend

docker push ghcr.io/your-org/algobattle-api:latest
docker push ghcr.io/your-org/algobattle-judge:latest
docker push ghcr.io/your-org/algobattle-frontend:latest
```

### 7. SSH into the API EC2 and start the stack

```bash
ssh -i ~/.ssh/algobattle-prod.pem ubuntu@<api_host>

# On the EC2:
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu

# Clone the repo (or use a deployment script via CI)
git clone https://github.com/your-org/algobattle.git
cd algobattle/infra

# Set environment — use values from Terraform outputs + Secrets Manager
# The EC2 IAM role has permissions to fetch secrets automatically
cat <<EOF > .env
DATABASE_URL=postgresql+asyncpg://algobattle:<password>@<rds_endpoint>/algobattle
REDIS_URL=redis://<redis_endpoint>:6379/0
JUDGE0_URL=http://<judge0_host>:2358
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=<password from RDS>
EOF

docker compose up -d
```

---

## Estimated Monthly Cost (dev tier, us-east-1)

| Resource | Spec | Est. $/mo |
|---|---|---|
| ALB | Application LB | ~$22 |
| EC2 API + worker | t3.small, gp3 50 GB | ~$20 |
| EC2 Judge0 | t3.medium, gp3 80 GB | ~$36 |
| RDS PostgreSQL | db.t4g.micro, 20 GB | ~$16 |
| ElastiCache Redis | cache.t4g.micro | ~$15 |
| NAT Gateway | 1 × nat-xxx | ~$33 |
| EIP | 1 attached | ~$3 |
| Data transfer | estimate | ~$5 |
| **Total** | | **~$150/mo** |

**Cost tips:** Use `vpc_az_count = 1` and `enable_nat_gateway = false` for dev to drop to ~$80/mo. Use Spot instances for the judge EC2 (saves 60–70%).

---

## Verify the Deployment

```bash
# Check ALB health
curl https://algobattle.example.com/api/health

# Expected: {"status":"ok","database":"ok","redis":"ok"}

# Check Judge0
curl http://<judge0_host>:2358/

# Check worker queue
docker exec algobattle-api python -c "import redis; r = redis.from_url('$REDIS_URL'); print(r.llen('rq:queue:algobattle-judge'))"

# Smoke test
cd algobattle/infra && ./scripts/smoke-test.sh
```

---

## Teardown (Avoid Lingering Resources)

```bash
# Destroy all Terraform-managed resources
cd algobattle/infra/terraform/aws
terraform destroy -var-file=environments/dev.tfvars

# Remove any manually created resources
# - RDS snapshot retention: AWS Console → RDS → Automated backups → disable
# - ECR repositories: aws ecr delete-repository --repository-name algobattle-api
# - S3 bucket for Terraform state (if local): rm -rf terraform.tfstate*

# Verify nothing remains
aws ec2 describe-instances --filters "Name=tag:Project,Values=algobattle" --query "Reservations[*].Instances[*].InstanceId"
```

---

## How to Modify and Customize

The Terraform layout is intentionally modular. Common customizations:

**Use a custom domain + free HTTPS:**
```
domain_name = "contest.yoursite.com"   # set in dev.tfvars
terraform apply                        # ACM cert auto-requested via DNS
```

**Scale up for more users:**
```hcl
# environments/prod.tfvars
api_instance_type    = "t3.large"      # more API concurrency
judge0_instance_type = "t3.xlarge"   # faster compilation in Judge0
db_instance_class     = "db.t4g.small" # more DB connections
```

**Switch to Multi-AZ (HA):**
```hcl
db_multi_az         = true
vpc_az_count         = 2
enable_nat_gateway   = true
```

**Add GitHub Actions CI/CD** (already in `infra/.github/workflows/`):
```yaml
# .github/workflows/deploy.yml
- name: Deploy to EC2
  uses: appleboy/ssh-action@master
  with:
    host: ${{ secrets.AWS_API_HOST }}
    key: ${{ secrets.SSH_KEY }}
    script: |
      cd algobattle/infra
      docker compose pull
      docker compose up -d --no-deps
```

**Replace EC2 with ECS/Fargate:** Replace the `compute` module with an ECS task definition using the same Docker images. The Helm chart in `infra/helm/` is the K8s equivalent for EKS deployments.
