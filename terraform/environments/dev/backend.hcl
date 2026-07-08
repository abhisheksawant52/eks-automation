# Partial backend configuration for the dev environment.
# Uncomment the S3 backend block in terraform/versions.tf, then run:
#   terraform -chdir=terraform init -backend-config=environments/dev/backend.hcl
bucket         = "my-terraform-state-dev"
key            = "eks-automation/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-locks"
encrypt        = true
