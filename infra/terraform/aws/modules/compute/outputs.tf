output "api_instance_id" {
  value = aws_instance.api.id
}

output "api_public_dns" {
  value = aws_instance.api.public_dns
}

output "api_public_ip" {
  value = aws_eip.api.public_ip
}

output "api_security_group_id" {
  value = aws_security_group.api.id
}