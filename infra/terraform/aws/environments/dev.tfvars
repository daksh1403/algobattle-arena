# ============================================================================
# dev.tfvars — smallest possible footprint, no domain, single AZ
# ============================================================================
aws_region   = "us-east-1"
environment  = "dev"
project_name = "algobattle-dev"

domain_name         = ""
acm_certificate_arn = ""

# Single AZ, no NAT — instance has public IP
vpc_az_count       = 1
enable_nat_gateway = false

# Smallest reasonable instances for dev
api_instance_type    = "t3.small"
judge0_instance_type = "t3.medium"

# db.t4g.micro is free-tier-eligible
db_instance_class        = "db.t4g.micro"
db_allocated_storage     = 20
db_max_allocated_storage = 50
db_multi_az              = false

ssh_key_name = "algobattle-dev"
# Tighter SSH for dev
ssh_allowed_cidrs = ["0.0.0.0/0"]

# Container images (override after first CI run)
image_api      = "ghcr.io/your-org/algobattle-api:dev"
image_judge    = "ghcr.io/your-org/algobattle-judge:dev"
image_frontend = "ghcr.io/your-org/algobattle-frontend:dev"
github_org     = "your-org"