output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "port" {
  value = aws_db_instance.main.port
}

output "address" {
  value = aws_db_instance.main.address
}

output "security_group_id" {
  value = aws_security_group.rds.id
}

output "secret_arn" {
  value     = aws_secretsmanager_secret.db.arn
  sensitive = true
}