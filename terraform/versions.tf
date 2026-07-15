terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.54"
    }
  }

  # Remote state backend. Configure per environment with a partial backend, e.g.
  #   terraform init -backend-config=environments/dev/backend.hcl
  # backend "s3" {
  #   bucket         = "my-terraform-state"
  #   key            = "eks-automation/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-locks"
  #   encrypt        = true
  # }
}
