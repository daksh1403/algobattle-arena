# ============================================================================
# Outputs — handy after `terraform apply`
# ============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.network.private_subnet_ids
}

output "api_instance_id" {
  description = "EC2 instance ID running the API"
  value       = module.compute.api_instance_id
}

output "api_host" {
  description = "Public DNS of the API EC2 (SSH here)"
  value       = module.compute.api_public_dns
}

output "judge0_host" {
  description = "Public DNS of the Judge0 EC2"
  value       = module.judge0.public_dns
}

output "ssh_command_api" {
  description = "Copy-paste SSH command for the API host"
  value       = "ssh -i ~/.ssh/${var.ssh_key_name}.pem ubuntu@${module.compute.api_public_dns}"
}

output "ssh_command_judge0" {
  description = "Copy-paste SSH command for the Judge0 host"
  value       = "ssh -i ~/.ssh/${var.ssh_key_name}.pem ubuntu@${module.judge0.public_dns}"
}

output "rds_endpoint" {
  description = "RDS endpoint (host:port)"
  value       = module.database.endpoint
}

output "rds_secret_arn" {
  description = "Secrets Manager ARN with the DB password"
  value       = module.database.secret_arn
  sensitive   = true
}

output "alb_dns_name" {
  description = "Public DNS of the ALB"
  value       = aws_lb.main.dns_name
}

output "deployment_command" {
  description = "Run this from CI/CD to deploy after images are pushed"
  value       = "ssh -i ~/.ssh/${var.ssh_key_name}.pem ubuntu@${module.compute.api_public_dns} '/home/ubuntu/algobattle/deploy.sh'"
}