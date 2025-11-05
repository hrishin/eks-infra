# Node Groups Module

This module creates managed EKS node groups with launch templates.

## Features

- Support for multiple instance types
- Launch templates with custom configuration
- Automatic GPU detection and labeling
- Custom labels and taints
- Configurable scaling (min, max, desired size)
- Custom disk sizes

## Usage

```hcl
module "node_groups" {
  source = "./modules/node-groups"

  cluster_name                    = "my-cluster"
  node_groups                     = var.node_groups_config
  node_group_service_role_arn     = module.eks_cluster.node_group_service_role_arn
  cluster_security_group_id       = module.eks_cluster.cluster_security_group_id
  worker_node_security_group_id  = module.networking.worker_node_security_group_id
  private_subnet_ids              = module.networking.private_subnet_ids
}
```

## GPU Support

The module automatically detects GPU instance types (P and G series) and:
- Adds GPU-specific labels
- Adds GPU taints if not already specified

Supported GPU types:
- P3: Tesla V100
- P4: A100
- G4: T4
- G5: A10G
- G6: L4

