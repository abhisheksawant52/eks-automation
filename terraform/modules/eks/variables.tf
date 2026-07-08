variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for the control plane."
  type        = string
  default     = "1.30"
}

variable "vpc_id" {
  description = "VPC in which the cluster security group is created."
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the control plane and node group."
  type        = list(string)
}

variable "endpoint_public_access" {
  description = "Enable public access to the Kubernetes API server."
  type        = bool
  default     = true
}

variable "endpoint_private_access" {
  description = "Enable private access to the Kubernetes API server."
  type        = bool
  default     = false
}

variable "enabled_cluster_log_types" {
  description = "Control plane log types to ship to CloudWatch."
  type        = list(string)
  default     = ["api", "audit", "authenticator"]
}

variable "node_group_name" {
  description = "Name of the managed node group."
  type        = string
  default     = "default"
}

variable "instance_types" {
  description = "EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "ami_type" {
  description = "AMI type for the managed node group."
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 10
}

variable "desired_size" {
  description = "Desired number of worker nodes."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags applied to all EKS resources."
  type        = map(string)
  default     = {}
}
