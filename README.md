## EKS Pulumi Infrastructure

This repository contains a Pulumi program and supporting configuration for provisioning and managing an Amazon EKS cluster along with common add-ons.

## Infrastructure is provisions
- netowrking stack - VP to subnets
- EKS cluster and node groups
- Bootstraps the flux for the gitops as put the cluster configuration `clusters/prod/extensions`

### Prerequisites
- Install the Pulumi CLI and configure AWS credentials with sufficient permissions.
- Optionally create and activate a Python virtual environment, then run `pip install -r requirements.txt`.

### Quick Start
1. Bootstrap environment-specific secrets and configuration with `./setup-pulumi.sh`.
2. Preview the cluster deployment and its extensions with `./quick-start.sh`.
3. Deploy the cluster `pulumi -C clusters/prod/infra up`

### Repository Layout
- `clusters/`: Environment-specific cluster definitions and Pulumi stacks.
- `iac-modules/`: Reusable Pulumi components for cluster infrastructure and extensions.
- `config/`: Encrypted configuration values for supported environments.

