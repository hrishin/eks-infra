# Kubernetes Add-ons (Cilium, CoreDNS)
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/terraform/modules/kubernetes-addons"
}

# Generate provider configuration for Kubernetes and Helm
generate "providers" {
  path      = "providers.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "kubernetes" {
  host                   = var.cluster_endpoint
  cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
  token                  = data.aws_eks_cluster_auth.main.token
}

provider "helm" {
  kubernetes {
    host                   = var.cluster_endpoint
    cluster_ca_certificate = base64decode(var.cluster_ca_certificate)
    token                  = data.aws_eks_cluster_auth.main.token
  }
}
EOF
}

dependency "eks-cluster" {
  config_path = "../eks-cluster"
  
  mock_outputs = {
    cluster_id                = "infra-cluster"
    cluster_endpoint          = "https://example.eks.amazonaws.com"
    cluster_ca_certificate    = "LS0tLS1CRUdJTi..."
  }
  
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  cluster_name           = dependency.eks-cluster.outputs.cluster_id
  cluster_endpoint       = dependency.eks-cluster.outputs.cluster_endpoint
  cluster_ca_certificate = dependency.eks-cluster.outputs.cluster_certificate_authority_data
  pod_cidr_range         = "10.0.0.0/16"
  enable_cilium          = true
  enable_coredns         = true
  node_role_arn          = dependency.eks-cluster.outputs.node_group_service_role_arn
  cluster_admin_user_arns = [
    "arn:aws:iam::203070858830:user/hrishi"
  ]
}

