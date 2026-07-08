output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = module.eks.cluster_name
}

output "cluster_arn" {
  description = "ARN of the EKS cluster."
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Endpoint of the Kubernetes API server."
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "Kubernetes version of the cluster."
  value       = module.eks.cluster_version
}

output "cluster_security_group_id" {
  description = "Security group ID managed by the EKS control plane."
  value       = module.eks.cluster_security_group_id
}

output "cluster_certificate_authority" {
  description = "Base64-encoded certificate authority data."
  value       = module.eks.cluster_certificate_authority
  sensitive   = true
}

output "cluster_role_arn" {
  description = "IAM role ARN of the EKS control plane."
  value       = module.eks.cluster_role_arn
}

output "node_role_arn" {
  description = "IAM role ARN of the managed node group."
  value       = module.eks.node_role_arn
}

output "vpc_id" {
  description = "VPC ID where the cluster is deployed."
  value       = module.vpc.vpc_id
}

output "subnet_ids" {
  description = "Public subnet IDs used by the cluster."
  value       = module.vpc.public_subnet_ids
}

output "kubeconfig_command" {
  description = "AWS CLI command to update kubeconfig."
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}
