# EKS Pulumi Infrastructure - Modular Structure

This project provides a modular approach to creating AWS EKS infrastructure using Pulumi. The code has been refactored into separate modules for better organization and maintainability.

## Project Structure

```
eks-pulumni/
├── __main__.py                 # Main entry point
├── node-groups.yaml           # Node group configuration
├── modules/
│   ├── __init__.py
│   ├── shared/                # Shared utilities and configuration
│   │   ├── __init__.py
│   │   └── config.py          # Configuration loading functions
│   ├── networking/            # Networking infrastructure
│   │   ├── __init__.py
│   │   └── networking.py      # VPC, subnets, NAT gateways, security groups
│   ├── cluster/               # EKS cluster infrastructure
│   │   ├── __init__.py
│   │   └── cluster.py         # EKS cluster, IAM roles, OIDC provider
│   ├── nodegroup/             # Node group management
│   │   ├── __init__.py
│   │   └── nodegroup.py       # Launch templates, autoscaling groups
│   ├── cilium/                # Cilium CNI with kube-proxy replacement
│   │   ├── __init__.py
│   │   └── cilium.py          # Cilium CNI installation and configuration
│   └── coredns/               # CoreDNS installation
│       ├── __init__.py
│       └── coredns.py         # CoreDNS installation using Helm
└── README.md
```

## Modules Overview

### 1. Shared Module (`modules/shared/`)
- **Purpose**: Common utilities and configuration management
- **Key Functions**:
  - `get_pulumi_config()`: Loads Pulumi configuration
  - `load_node_groups_config()`: Loads node group configuration from YAML

### 2. Networking Module (`modules/networking/`)
- **Purpose**: Manages all networking infrastructure
- **Key Components**:
  - VPC creation and configuration
  - Public and private subnets across multiple AZs
  - Internet Gateway and NAT Gateways
  - Route tables and associations
  - Security groups for worker nodes

### 3. Cluster Module (`modules/cluster/`)
- **Purpose**: Manages EKS cluster and related IAM resources
- **Key Components**:
  - EKS cluster creation
  - IAM roles for cluster and node groups
  - OIDC identity provider
  - AWS Auth ConfigMap for node authentication
  - Kubeconfig generation

### 4. Node Group Module (`modules/nodegroup/`)
- **Purpose**: Manages self-managed node groups
- **Key Components**:
  - Launch templates with EKS-optimized AMIs
  - Autoscaling groups for node management
  - User data scripts for node bootstrap
  - Instance profiles and security group associations

### 5. Cilium CNI Module (`modules/cilium/`)
- **Purpose**: Installs and configures Cilium CNI with full kube-proxy replacement
- **Key Features**:
  - Full kube-proxy replacement (strict mode)
  - ENI-based IPAM for AWS integration
  - Hubble observability enabled
  - Prometheus metrics enabled
  - Host services and external IPs support
  - NodePort and HostPort support

### 6. CoreDNS Module (`modules/coredns/`)
- **Purpose**: Installs CoreDNS using Helm chart
- **Key Features**:
  - Standard kube-dns IP (10.100.0.10)
  - Kubernetes service discovery
  - Prometheus metrics enabled
  - Configurable upstream DNS resolution
  - Health checks and readiness probes

## Configuration

### Pulumi Configuration
Set the following in your Pulumi configuration:

```bash
pulumi config set cluster_name "my-eks-cluster"
pulumi config set cluster_version "1.28"
pulumi config set region "us-west-2"
```

### Node Groups Configuration
Configure node groups in `node-groups.yaml`:

```yaml
node_groups:
  core:
    instance_types: ["t3.medium"]
    desired_size: 3
    min_size: 3
    max_size: 4
    disk_size: 20
  gpu-worker:
    instance_types: ["g5.xlarge"]
    desired_size: 2
    min_size: 1
    max_size: 5
    disk_size: 50
```

## Cilium CNI Configuration

The Cilium CNI is configured with the following features:

- **Kube-proxy Replacement**: Full replacement in strict mode
- **IPAM**: ENI-based IPAM for AWS integration
- **Observability**: Hubble UI and relay enabled
- **Metrics**: Prometheus metrics enabled
- **Networking**: Support for NodePort, HostPort, ExternalIPs, and Host Services

### Cilium Features Enabled:
- `kubeProxyReplacement: strict` - Complete kube-proxy replacement
- `ipam.mode: eni` - ENI-based IPAM for AWS
- `hubble.enabled: true` - Network observability
- `prometheus.enabled: true` - Metrics collection

## CoreDNS Configuration

CoreDNS is installed with standard Kubernetes DNS configuration:

- **Service IP**: 10.100.0.10 (standard kube-dns IP)
- **Replicas**: 2 for high availability
- **Plugins**: Kubernetes service discovery, health checks, caching
- **Metrics**: Prometheus metrics on port 9153

## Usage

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Pulumi**:
   ```bash
   pulumi config set cluster_name "your-cluster-name"
   pulumi config set cluster_version "1.28"
   pulumi config set region "us-west-2"
   ```

3. **Deploy Infrastructure**:
   ```bash
   pulumi up
   ```

4. **Get Kubeconfig**:
   ```bash
   pulumi stack output kubeconfig > kubeconfig.yaml
   export KUBECONFIG=kubeconfig.yaml
   ```

## Benefits of Modular Structure

1. **Separation of Concerns**: Each module handles a specific aspect of the infrastructure
2. **Reusability**: Modules can be easily reused in other projects
3. **Maintainability**: Easier to maintain and update specific components
4. **Testability**: Individual modules can be tested in isolation
5. **Scalability**: Easy to add new modules or extend existing ones

## Key Features

- **Self-managed Node Groups**: Uses Auto Scaling Groups with custom launch templates
- **Multi-AZ Deployment**: Automatically distributes resources across 3 availability zones
- **Security**: Implements proper security groups and IAM roles
- **OIDC Integration**: Enables IRSA (IAM Roles for Service Accounts)
- **AWS Auth ConfigMap**: Automatically configures node authentication
- **Comprehensive Logging**: Enables EKS control plane logging
- **Cilium CNI**: Advanced networking with full kube-proxy replacement and ENI-based IPAM
- **CoreDNS**: Reliable DNS resolution with Prometheus metrics
- **Helm Integration**: Uses Helm charts for CNI and DNS installation

## Exports

The infrastructure exports the following values:
- `cluster_name`: Name of the EKS cluster
- `cluster_endpoint`: EKS cluster API endpoint
- `cluster_security_group_id`: Security group ID for the cluster
- `worker_node_security_group_id`: Security group ID for worker nodes
- `cluster_oidc_issuer`: OIDC issuer URL
- `cluster_oidc_provider_arn`: OIDC provider ARN
- `node_group_service_role_arn`: IAM role ARN for node groups
- `vpc_id`: VPC ID
- `public_subnet_ids`: List of public subnet IDs
- `private_subnet_ids`: List of private subnet IDs
- `kubeconfig`: Complete kubeconfig for cluster access
- `managed_node_group_names`: List of managed node group names
- `cilium_release_name`: Name of the Cilium Helm release
- `coredns_release_name`: Name of the CoreDNS Helm release
