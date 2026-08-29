# ============================================================================
# prod.tfvars — production sizing. Domain + cert required.
# ============================================================================
aws_region   = "us-east-1"
environment  = "prod"
project_name = "algobattle"

# Update to your real domain
domain_name         = "algobattle.example.com"
acm_certificate_arn = ""

# 2 AZs for some HA (more cost; ~$33 extra for second NAT)
vpc_az_count       = 2
enable_nat_gateway = true

# Production sizing
api_instance_type = "t3.medium"
api_volume_size   = 50

judge0_instance_type = "t3.large"
judge0_volume_size   = 80

db_instance_class        = "db.t4g.micro" # bump to db.t4g.small when > 100 connections
db_allocated_storage     = 50
db_max_allocated_storage = 200
db_multi_az              = true

ssh_key_name = "algobattle-prod"
# Tighten to your office / VPN CIDR before applying
ssh_allowed_cidrs = ["0.0.0.0/0"]

image_api      = "ghcr.io/your-org/algobattle-api:latest"
image_judge    = "ghcr.io/your-org/algobattle-judge:latest"
image_frontend = "ghcr.io/your-org/algobattle-frontend:latest"
github_org     = "your-org"