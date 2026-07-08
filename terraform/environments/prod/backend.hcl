# Partial backend configuration for the prod environment.
# Uncomment the S3 backend block in terraform/versions.tf, then run:
#   terraform -chdir=terraform init -backend-config=environments/prod/backend.hcl
bucket         = "my-terraform-state-prod"
key            = "eks-automation/prod/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-locks"
encrypt        = true
