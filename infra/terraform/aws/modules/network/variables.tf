variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_cidr" { type = string }
variable "az_count" {
  type    = number
  default = 1
}
variable "enable_nat_gateway" {
  type    = bool
  default = true
}