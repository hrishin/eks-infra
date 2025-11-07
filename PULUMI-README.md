# EKS Infrastructure with Pulumi

This directory contains a complete Pulumi conversion of the Terraform/Terragrunt EKS infrastructure setup. All original Terraform code has been preserved in the `terraform/` and `clusters/` directories.

## Overview

This Pulumi project creates a production-ready EKS cluster on AWS with:

- **Networking**: VPC with public/private subnets, NAT gateways, and security groups
- **EKS Cluster**: Managed Kubernetes cluster with OIDC provider and access entries
- **Self-Managed Node Groups**: Auto-scaling groups with custom launch templates
- **AWS Auth ConfigMap**: Automatic node and user authentication setup
- **Cilium CNI**: Advanced networking with kube-proxy replacement and ENI-based IPAM
- **CoreDNS**: DNS resolution for Kubernetes services

## Project Structure

```
eks-pulumni/
├── Pulumi.yaml                   # Pulumi project configuration
├── __main__.py                   # Main orchestration file
├── requirements.txt              # Python dependencies
├── node-groups.yaml             # Node group configuration
├── setup-pulumi.sh              # Setup script
├── pulumi_modules/              # Pulumi modules
│   ├── shared/                  # Shared utilities and config
│   │   └── config.py
│   ├── networking/              # VPC, subnets, security groups
│   │   └── networking.py
│   ├── eks_cluster/             # EKS cluster and IAM
│   │   └── cluster.py
│   ├── node_groups/             # Self-managed node groups
│   │   └── node_groups.py
│   ├── eks_auth/                # aws-auth ConfigMap
│   │   └── auth.py
│   └── kubernetes_addons/       # Cilium and CoreDNS
│       └── addons.py
├── terraform/                   # Original Terraform modules (preserved)
└── clusters/                    # Original Terragrunt configs (preserved)
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Python 3.8+** installed
3. **Pulumi CLI** installed ([Installation guide](https://www.pulumi.com/docs/get-started/install/))
4. AWS account with permissions to create EKS, VPC, IAM resources

## Quick Start

### 1. Setup

Run the setup script to create a virtual environment and install dependencies:

```bash
chmod +x setup-pulumi.sh
./setup-pulumi.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Login to Pulumi

Choose your backend (local or Pulumi Cloud):

```bash
# Local backend (stores state locally)
pulumi login --local

# Or Pulumi Cloud (recommended for teams)
pulumi login
```

### 3. Create a Stack

```bash
pulumi stack init prod
```

### 4. Configure (Optional)

The project has sensible defaults configured in `Pulumi.yaml`. You can override them:

```bash
# AWS region
pulumi config set aws:region eu-west-2

# Cluster configuration
pulumi config set eks-pulumi:cluster_name infra-cluster
pulumi config set eks-pulumi:cluster_version 1.33

# Networking
pulumi config set eks-pulumi:vpc_cidr 10.0.0.0/16
pulumi config set eks-pulumi:availability_zones "eu-west-2a,eu-west-2c"

# Admin access
pulumi config set eks-pulumi:cluster_admin_user_arns "arn:aws:iam::203070858830:user/hrishi"

# Add-ons
pulumi config set eks-pulumi:enable_cilium true
pulumi config set eks-pulumi:enable_coredns true
```

### 5. Deploy

Preview the changes:

```bash
pulumi preview
```

Deploy the infrastructure:

```bash
pulumi up
```

This will create approximately 50+ resources including:
- VPC with 2 public and 2 private subnets
- NAT gateways and routing tables
- EKS cluster
- IAM roles and policies
- OIDC provider
- Node groups (as configured in `node-groups.yaml`)
- Cilium CNI
- CoreDNS

### 6. Access the Cluster

Get the kubeconfig:

```bash
pulumi stack output kubeconfig > kubeconfig.yaml
export KUBECONFIG=$(pwd)/kubeconfig.yaml
```

Or configure kubectl directly:

```bash
aws eks update-kubeconfig --region eu-west-2 --name infra-cluster
```

Verify access:

```bash
kubectl get nodes
kubectl get pods -A
```

## Configuration

### Node Groups

Node groups are configured in `node-groups.yaml`. The format is:

```yaml
node_groups:
  core:
    instance_types: ["t3.large"]
    desired_size: 2
    min_size: 2
    max_size: 4
    disk_size: 20
    ami_id: "ami-060bb37b943ff8d8e"
    labels:
      node-type: "core"
      workload: "general"
    taints:
      - key: "node-type"
        value: "core"
        effect: "NoSchedule"
```

### Pulumi Configuration

Key configuration options:

| Config Key | Description | Default |
|-----------|-------------|---------|
| `aws:region` | AWS region | eu-west-2 |
| `eks-pulumi:cluster_name` | EKS cluster name | infra-cluster |
| `eks-pulumi:cluster_version` | Kubernetes version | 1.33 |
| `eks-pulumi:vpc_cidr` | VPC CIDR block | 10.0.0.0/16 |
| `eks-pulumi:availability_zones` | AZs (comma-separated) | eu-west-2a,eu-west-2c |
| `eks-pulumi:cluster_admin_user_arns` | Admin user ARNs | - |
| `eks-pulumi:enable_cilium` | Enable Cilium CNI | true |
| `eks-pulumi:enable_coredns` | Enable CoreDNS | true |

## Module Details

### 1. Networking Module

Creates:
- VPC with DNS support
- Public subnets (for load balancers)
- Private subnets (for worker nodes)
- Internet Gateway
- NAT Gateways (one per AZ)
- Route tables and associations
- Worker node security group

### 2. EKS Cluster Module

Creates:
- EKS cluster
- Cluster IAM role with policies
- Node IAM role with policies
- Instance profile for nodes
- OIDC identity provider
- EKS access entries for admins
- EKS access entry for node role

### 3. Node Groups Module

Creates:
- Launch templates with:
  - EKS-optimized AMI
  - User data for cluster bootstrap
  - Security groups
  - IAM instance profile
- Auto Scaling Groups with:
  - Desired/min/max capacity
  - Health checks
  - Subnet distribution

### 4. EKS Auth Module

Creates:
- aws-auth ConfigMap in kube-system
- Maps node IAM role to Kubernetes RBAC
- Maps admin users to system:masters group

### 5. Kubernetes Add-ons Module

Installs via Helm:
- **Cilium CNI**: 
  - ENI-based IPAM
  - Kube-proxy replacement
  - Hubble for observability
- **CoreDNS**: 
  - DNS service discovery
  - Prometheus metrics

## Outputs

After deployment, the following outputs are available:

```bash
pulumi stack output cluster_name              # EKS cluster name
pulumi stack output cluster_endpoint          # Cluster API endpoint
pulumi stack output cluster_arn               # Cluster ARN
pulumi stack output vpc_id                    # VPC ID
pulumi stack output public_subnet_ids         # Public subnet IDs
pulumi stack output private_subnet_ids        # Private subnet IDs
pulumi stack output kubeconfig                # Complete kubeconfig
```

## Management Commands

### Update Infrastructure

```bash
pulumi up
```

### Destroy Infrastructure

```bash
pulumi destroy
```

### View Stack Outputs

```bash
pulumi stack output
```

### Refresh State

```bash
pulumi refresh
```

### View Stack Graph

```bash
pulumi stack graph stack.dot
dot -Tpng stack.dot -o stack.png
```

## Comparison with Terraform

### Similarities

- **Same Resources**: Creates identical AWS resources
- **Same Configuration**: Uses the same `node-groups.yaml` configuration
- **Same Architecture**: VPC, EKS cluster, node groups, add-ons

### Differences

| Aspect | Terraform/Terragrunt | Pulumi |
|--------|---------------------|--------|
| Language | HCL | Python |
| State Management | Terragrunt/S3 | Pulumi backend |
| Dependencies | Explicit via Terragrunt | Implicit via code |
| Type Safety | Limited | Full Python type hints |
| Testing | Complex | Standard Python testing |
| IDE Support | Limited | Full Python IDE support |
| Modularity | File-based | Function/class-based |

### Advantages of Pulumi

1. **Programming Language**: Use full Python capabilities (loops, conditionals, functions)
2. **Type Safety**: Catch errors before deployment with type hints
3. **Testing**: Use standard Python testing frameworks
4. **IDE Support**: IntelliSense, autocomplete, refactoring tools
5. **Sharing**: Publish modules to PyPI
6. **Integration**: Easy integration with Python tools and libraries

## Troubleshooting

### Authentication Issues

If nodes aren't joining the cluster:

```bash
# Check aws-auth ConfigMap
kubectl get configmap aws-auth -n kube-system -o yaml

# Verify node IAM role
pulumi stack output node_group_service_role_arn
```

### Networking Issues

If pods can't communicate:

```bash
# Check Cilium status
kubectl exec -n kube-system ds/cilium -- cilium status

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=coredns
```

### State Issues

If Pulumi state is out of sync:

```bash
pulumi refresh
pulumi up
```

## Migration from Terraform

If you want to import existing Terraform-managed resources:

```bash
# Import VPC
pulumi import aws:ec2/vpc:Vpc infra-cluster-vpc vpc-xxxxx

# Import EKS cluster
pulumi import aws:eks/cluster:Cluster infra-cluster infra-cluster

# Continue for other resources...
```

## Contributing

When modifying the infrastructure:

1. Make changes in the appropriate module
2. Run `pulumi preview` to see changes
3. Run `pulumi up` to apply
4. Update this README if adding new features

## Support

For issues or questions:

1. Check Pulumi documentation: https://www.pulumi.com/docs/
2. Check AWS EKS documentation: https://docs.aws.amazon.com/eks/
3. Review module code in `pulumi_modules/`

## License

This infrastructure code is provided as-is for your use.

