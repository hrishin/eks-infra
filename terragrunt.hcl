# Root Terragrunt configuration
include "root" {
  path = "${get_repo_root()}/terragrunt/root.hcl"
}

# Generate provider configuration
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
EOF
}

# Load common variables
locals {
  common_vars = yamldecode(file("${get_repo_root()}/terragrunt/common.yaml"))
}

# Inputs
inputs = {
  aws_region = local.common_vars.aws_region
  tags       = local.common_vars.tags
}

