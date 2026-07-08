output "vpc_id" {
  description = "ID of the created VPC."
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets."
  value       = aws_subnet.public[*].id
}

output "availability_zones" {
  description = "Availability zones used by the subnets."
  value       = slice(data.aws_availability_zones.available.names, 0, var.subnet_count)
}
