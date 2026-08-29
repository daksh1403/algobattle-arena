# ============================================================================
# Provider configuration
# ============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.50" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
    tls    = { source = "hashicorp/tls", version = "~> 4.0" }
  }

  # Remote state — uncomment and configure for production
  # backend "s3" {
  #   bucket         = "algobattle-terraform-state"
  #   key            = "aws/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "algobattle-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "algobattle"
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = "platform@algobattle.example.com"
    }
  }
}