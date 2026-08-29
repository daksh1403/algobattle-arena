variable "project_name" { type = string }
variable "environment" { type = string }
variable "instance_type" { type = string }
variable "volume_size" { type = number }
variable "volume_type" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "ssh_key_name" { type = string }
variable "ssh_allowed_cidrs" { type = list(string) }

variable "image_api" { type = string }
variable "image_judge" { type = string }
variable "image_frontend" { type = string }
variable "github_org" { type = string }

variable "rds_endpoint" { type = string }
variable "rds_port" { type = number }
variable "db_secret_arn" { type = string }

variable "rds_security_group_id" { type = string }
variable "judge0_security_group_id" {
  type    = string
  default = ""
}