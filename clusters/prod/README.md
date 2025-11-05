# Production Environment

This directory contains the Terragrunt configuration for the production environment.

## Deployment Order

The modules should be deployed in the following order:

1. **networking** - Creates VPC, subnets, NAT gateways, and worker node security group
2. **eks-cluster** - Creates EKS cluster, IAM roles, and OIDC provider
3. **node-groups** - Creates managed node groups
4. **kubernetes-addons** - Installs Cilium CNI and CoreDNS

## After Initial Deployment

After the cluster is created, you may need to update the networking module to add the cluster security group ID to the worker node security group:

```bash
cd networking
# Update terragrunt.hcl to include cluster_security_group_id from eks-cluster output
terragrunt apply
```

## Usage

### Deploy all modules

```bash
# From the project root
terragrunt run-all apply
```

### Deploy individual module

```bash
cd terragrunt/environments/prod/networking
terragrunt apply
```

### Destroy all modules (in reverse order)

```bash
terragrunt run-all destroy
```

