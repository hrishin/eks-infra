# Node Groups infrastructure
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/terraform/modules/node-groups"
}

dependency "networking" {
  config_path = "../networking"
  
  mock_outputs = {
    worker_node_security_group_id = "sg-12345"
    private_subnet_ids             = ["subnet-11111", "subnet-22222", "subnet-33333"]
  }
  
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "eks-cluster" {
  config_path = "../eks-cluster"
  
  mock_outputs = {
    cluster_security_group_id    = "sg-cluster-12345"
    node_group_service_role_arn  = "arn:aws:iam::123456789012:role/node-group-role"
    node_instance_profile_name   = "eks-node-instance-profile"
    cluster_endpoint             = "https://FFFFFFFF.gr7.us-east-1.eks.amazonaws.com"
    cluster_certificate_authority_data = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t\n..."
  }
  
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Load node groups configuration
locals {
  node_groups_config = yamldecode(file("${get_repo_root()}/node-groups.yaml"))
}

inputs = {
  cluster_name                    = "infra-cluster"
  node_groups                     = local.node_groups_config.node_groups
  node_group_service_role_arn     = dependency.eks-cluster.outputs.node_group_service_role_arn
  cluster_security_group_id       = dependency.eks-cluster.outputs.cluster_security_group_id
  worker_node_security_group_id  = dependency.networking.outputs.worker_node_security_group_id
  private_subnet_ids              = dependency.networking.outputs.private_subnet_ids
  node_instance_profile_name      = dependency.eks-cluster.outputs.node_instance_profile_name
  cluster_endpoint                = dependency.eks-cluster.outputs.cluster_endpoint
  cluster_certificate_authority_data = dependency.eks-cluster.outputs.cluster_certificate_authority_data
}

