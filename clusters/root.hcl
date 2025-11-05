# Root Terragrunt configuration
# Generate provider configuration
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}
EOF
}

# Common configuration
locals {
  aws_region = "eu-west-2"
  tags = {
    Environment = "production"
    ManagedBy   = "terragrunt"
    Project     = "eks-cluster"
  }
}

# Inputs
inputs = {
  aws_region = local.aws_region
  tags       = local.tags
}

