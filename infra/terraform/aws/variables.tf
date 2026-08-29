# ============================================================================
# Algobattle AWS — input variables
# ============================================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev / staging / prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project prefix used in resource names"
  type        = string
  default     = "algobattle"
}

variable "domain_name" {
  description = "Public domain (e.g. algobattle.example.com) — used for ALB + ACM"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "Pre-existing ACM cert ARN. If empty and domain_name is set, a new one is requested."
  type        = string
  default     = ""
}

# ----------------------------------------------------------------------------
# Network
# ----------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR for the new VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "vpc_az_count" {
  description = "Number of AZs (1 = single-AZ, cheapest; 2 = HA-lite)"
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2, 3], var.vpc_az_count)
    error_message = "vpc_az_count must be 1, 2, or 3."
  }
}

variable "enable_nat_gateway" {
  description = "Whether to deploy a NAT gateway (needed for private subnets to reach internet)"
  type        = bool
  default     = true
}

# ----------------------------------------------------------------------------
# Compute — API + worker EC2
# ----------------------------------------------------------------------------
variable "api_instance_type" {
  description = "EC2 instance type for API + workers"
  type        = string
  default     = "t3.medium"
}

variable "api_volume_size" {
  description = "Root volume size in GB for API EC2"
  type        = number
  default     = 50
}

variable "api_volume_type" {
  description = "EBS volume type"
  type        = string
  default     = "gp3"
}

# ----------------------------------------------------------------------------
# Compute — Judge0 EC2 (isolated)
# ----------------------------------------------------------------------------
variable "judge0_instance_type" {
  description = "EC2 instance type for Judge0 cluster"
  type        = string
  default     = "t3.large"
}

variable "judge0_volume_size" {
  description = "Root volume size in GB for Judge0 EC2"
  type        = number
  default     = 80
}

# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Initial storage in GB"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Max storage autoscaling ceiling in GB"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "algobattle"
}

variable "db_username" {
  description = "Master DB username"
  type        = string
  default     = "algobattle"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS (more cost, more HA)"
  type        = bool
  default     = false
}

# ----------------------------------------------------------------------------
# SSH
# ----------------------------------------------------------------------------
variable "ssh_key_name" {
  description = "Name of the EC2 key pair to install (must already exist in AWS)"
  type        = string
  default     = "algobattle-prod"
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs allowed to SSH into the EC2s (default: anywhere — tighten in prod)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ----------------------------------------------------------------------------
# Container images
# ----------------------------------------------------------------------------
variable "image_api" {
  type    = string
  default = "ghcr.io/your-org/algobattle-api:latest"
}

variable "image_judge" {
  type    = string
  default = "ghcr.io/your-org/algobattle-judge:latest"
}

variable "image_frontend" {
  type    = string
  default = "ghcr.io/your-org/algobattle-frontend:latest"
}

variable "github_org" {
  description = "GHCR owner / GitHub org"
  type        = string
  default     = "your-org"
}