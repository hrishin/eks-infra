# EKS Cluster infrastructure
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/terraform/modules/eks-cluster"
}

# Generate provider configuration for Kubernetes
generate "kubernetes_provider" {
  path      = "kubernetes_provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "kubernetes" {
  host                   = aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.main.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.main.token
}
EOF
}

dependency "networking" {
  config_path = "../networking"
  
  mock_outputs = {
    public_subnet_ids  = ["subnet-12345", "subnet-67890", "subnet-abcdef"]
    private_subnet_ids = ["subnet-11111", "subnet-22222", "subnet-33333"]
  }
  
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "networking" {
  config_path = "../networking"
  
  mock_outputs = {
    public_subnet_ids  = ["subnet-12345", "subnet-67890", "subnet-abcdef"]
    private_subnet_ids = ["subnet-11111", "subnet-22222", "subnet-33333"]
  }
  
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  cluster_name       = "infra-cluster"
  cluster_version    = "1.33"
  public_subnet_ids  = dependency.networking.outputs.public_subnet_ids
  private_subnet_ids = dependency.networking.outputs.private_subnet_ids
  cluster_admin_user_arns = [
    "arn:aws:iam::203070858830:user/hrishi"
  ]
}

