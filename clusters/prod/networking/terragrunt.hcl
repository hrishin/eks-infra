# Networking infrastructure
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/terraform/modules/networking"
}

inputs = {
  cluster_name              = "infra-cluster"
  vpc_cidr                  = "10.0.0.0/16"
  availability_zones        = ["eu-west-2a", "eu-west-2c"] # Only use AZs with g4dn capacity
  cluster_security_group_id = "" # Will be updated after cluster is created
}
