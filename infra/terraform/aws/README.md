# Algobattle — AWS Terraform (cost-optimized)

## What this provisions

A single-AZ, single-VPC environment sized for 100s of active users:

| Resource | Spec | Approx $/mo |
|---|---|---|
| ALB | application | ~$22 |
| EC2 api+worker | t3.medium, gp3 50 GB | ~$40 |
| EC2 judge0      | t3.large, gp3 80 GB | ~$72 |
| RDS postgres    | db.t4g.micro, 20 GB | ~$16 |
| NAT gateway     | 1 (single AZ) | ~$33 |
| EIP             | 1 | ~$3 |
| Secrets + KMS   | — | ~$1 |
| CloudWatch logs | 7-day retention | ~$2 |
| **Total** | | **~$189/mo** |

Idle baseline: the t3.medium + t3.large earn CPU credits and can sit near zero.

## Layout

```
.
├── main.tf             # entry point — composes the modules
├── variables.tf
├── outputs.tf
├── provider.tf
├── modules/
│   ├── network/        # VPC, public/private subnets, IGW, NAT, SGs
│   ├── compute/        # EC2 instance + IAM role + userdata
│   ├── database/       # RDS postgres
│   └── judge0/         # dedicated EC2 for the Judge0 cluster
└── environments/
    ├── dev.tfvars
    └── prod.tfvars
```

## Usage

```bash
cd infra/terraform/aws
terraform init
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

Outputs (printed at end):
- `api_host`         — public DNS of the api EC2
- `judge0_host`      — public DNS of the judge0 EC2
- `rds_endpoint`     — connection string for the DB
- `ssh_command_api`  — `ssh -i <key> ubuntu@<host>` (copy-paste ready)

## Upgrade path

| Traffic | Recommendation |
|---|---|
| < 500 concurrent users | this stack (default) |
| 500 – 5 000 | Replace single EC2s with Auto Scaling Groups + Application Load Balancer target groups per ASG. Move RDS to db.t4g.small or Aurora Serverless v2. |
| 5 000+ | Move to EKS, replace this whole stack with the Helm chart in `../../helm`. |

## Networking

Single AZ keeps cost low. The NAT gateway lets private subnets reach the internet
(e.g. for `apt` updates) without exposing them. For higher availability, set
`vpc_az_count = 2` in the tfvars.

## Secrets

All sensitive values (DB password, JWT secret, Grafana admin pwd) are stored
in AWS Secrets Manager and exported as Terraform outputs. The `userdata.sh`
script on each EC2 fetches them via the IAM role (no credentials on disk).