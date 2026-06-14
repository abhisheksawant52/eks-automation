output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = aws_eks_cluster.main.name
}

output "cluster_arn" {
  description = "ARN of the EKS cluster."
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "Endpoint of the Kubernetes API server."
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "Kubernetes version of the cluster."
  value       = aws_eks_cluster.main.version
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster."
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "vpc_id" {
  description = "VPC ID where the cluster is deployed."
  value       = aws_vpc.eks.id
}

output "subnet_ids" {
  description = "Public subnet IDs used by the cluster."
  value       = aws_subnet.public[*].id
}

output "cluster_certificate_authority" {
  description = "Base64-encoded certificate authority data."
  value       = aws_eks_cluster.main.certificate_authority[0].data
  sensitive   = true
}

output "cluster_role_arn" {
  description = "IAM role ARN of the EKS cluster."
  value       = aws_iam_role.eks_cluster.arn
}

output "node_role_arn" {
  description = "IAM role ARN of the EKS node group."
  value       = aws_iam_role.eks_node.arn
}

output "kubeconfig_command" {
  description = "AWS CLI command to update kubeconfig."
  value       = "aws eks update-kubeconfig --name ${aws_eks_cluster.main.name} --region ${var.region}"
}
