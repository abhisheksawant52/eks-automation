locals {
  name = var.cluster_name
}

module "vpc" {
  source = "./modules/vpc"

  name         = local.name
  cluster_name = var.cluster_name
  vpc_cidr     = var.vpc_cidr
  subnet_count = var.subnet_count
  tags         = var.tags
}

module "eks" {
  source = "./modules/eks"

  cluster_name       = var.cluster_name
  kubernetes_version = var.kubernetes_version
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.public_subnet_ids

  endpoint_public_access  = var.endpoint_public_access
  endpoint_private_access = var.endpoint_private_access

  node_group_name = "${var.cluster_name}-nodes"
  instance_types  = var.instance_types
  ami_type        = var.ami_type
  min_size        = var.min_size
  max_size        = var.max_size
  desired_size    = var.desired_size

  tags = var.tags
}
