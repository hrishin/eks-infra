# Pulumi Conversion - Deployment Checklist

This checklist guides you through deploying your EKS infrastructure using Pulumi.

## ✅ Pre-Deployment Checklist

### 1. Prerequisites Installed

- [ ] Python 3.8 or higher
  ```bash
  python3 --version
  ```

- [ ] Pulumi CLI installed
  ```bash
  pulumi version
  ```
  If not installed: `curl -fsSL https://get.pulumi.com | sh`

- [ ] AWS CLI installed and configured
  ```bash
  aws --version
  aws sts get-caller-identity
  ```

- [ ] kubectl installed (for cluster access)
  ```bash
  kubectl version --client
  ```

### 2. AWS Permissions

Ensure your AWS credentials have permissions to create:
- [ ] VPC and networking resources
- [ ] EKS clusters
- [ ] IAM roles and policies
- [ ] EC2 instances and Auto Scaling Groups
- [ ] Security groups

### 3. Configuration Review

- [ ] Review `node-groups.yaml` for node group configuration
- [ ] Check desired instance types are available in your region
- [ ] Verify AMI IDs are correct for your region
- [ ] Review availability zones in configuration

## 📋 Deployment Steps

### Step 1: Setup Environment

- [ ] Run setup script
  ```bash
  ./setup-pulumi.sh
  ```
  
  Or manually:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### Step 2: Login to Pulumi

- [ ] Choose backend and login
  ```bash
  # Option 1: Pulumi Cloud (recommended for teams)
  pulumi login
  
  # Option 2: Local backend (for testing)
  pulumi login --local
  
  # Option 3: AWS S3 backend
  pulumi login s3://my-pulumi-state-bucket
  ```

### Step 3: Create Stack

- [ ] Initialize stack
  ```bash
  pulumi stack init prod
  ```

### Step 4: Configure Stack

- [ ] Review default configuration
  ```bash
  pulumi config
  ```

- [ ] Set AWS region (if different from default)
  ```bash
  pulumi config set aws:region eu-west-2
  ```

- [ ] Configure cluster admin users
  ```bash
  pulumi config set eks-pulumi:cluster_admin_user_arns "arn:aws:iam::ACCOUNT_ID:user/USERNAME"
  ```

- [ ] Review other settings (optional)
  ```bash
  pulumi config set eks-pulumi:cluster_name infra-cluster
  pulumi config set eks-pulumi:cluster_version 1.33
  pulumi config set eks-pulumi:vpc_cidr 10.0.0.0/16
  ```

### Step 5: Review Node Groups

- [ ] Edit `node-groups.yaml` if needed
- [ ] Verify instance types
- [ ] Check disk sizes
- [ ] Review labels and taints

### Step 6: Preview Deployment

- [ ] Run preview to see what will be created
  ```bash
  pulumi preview
  ```

- [ ] Review the output
  - Check resource count (~40-50 resources expected)
  - Verify resource types
  - Look for any errors or warnings

### Step 7: Deploy Infrastructure

- [ ] Deploy the stack
  ```bash
  pulumi up
  ```

- [ ] Review the deployment plan
- [ ] Type "yes" to confirm
- [ ] Wait for deployment (20-25 minutes typically)

### Step 8: Verify Deployment

- [ ] Check stack outputs
  ```bash
  pulumi stack output
  ```

- [ ] Export kubeconfig
  ```bash
  pulumi stack output kubeconfig > kubeconfig.yaml
  export KUBECONFIG=$(pwd)/kubeconfig.yaml
  ```

- [ ] Verify cluster access
  ```bash
  kubectl get nodes
  kubectl get pods -A
  ```

- [ ] Check nodes are ready
  ```bash
  kubectl get nodes -o wide
  ```

- [ ] Verify Cilium is running
  ```bash
  kubectl get pods -n kube-system -l k8s-app=cilium
  ```

- [ ] Verify CoreDNS is running
  ```bash
  kubectl get pods -n kube-system -l k8s-app=coredns
  ```

## 🔍 Post-Deployment Verification

### Networking

- [ ] VPC created
  ```bash
  pulumi stack output vpc_id
  aws ec2 describe-vpcs --vpc-ids $(pulumi stack output vpc_id)
  ```

- [ ] Subnets created (2 public, 2 private)
  ```bash
  pulumi stack output public_subnet_ids
  pulumi stack output private_subnet_ids
  ```

- [ ] NAT gateways operational
  ```bash
  aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$(pulumi stack output vpc_id)"
  ```

### EKS Cluster

- [ ] Cluster running
  ```bash
  aws eks describe-cluster --name $(pulumi stack output cluster_name)
  ```

- [ ] Cluster endpoint accessible
  ```bash
  pulumi stack output cluster_endpoint
  ```

- [ ] OIDC provider created
  ```bash
  pulumi stack output cluster_oidc_provider_arn
  ```

### Node Groups

- [ ] Auto Scaling Groups created
  ```bash
  pulumi stack output autoscaling_group_names
  ```

- [ ] Nodes joined cluster
  ```bash
  kubectl get nodes
  ```

- [ ] Node labels applied
  ```bash
  kubectl get nodes --show-labels
  ```

- [ ] Node taints applied (if configured)
  ```bash
  kubectl get nodes -o json | jq '.items[].spec.taints'
  ```

### Add-ons

- [ ] Cilium deployed
  ```bash
  kubectl exec -n kube-system ds/cilium -- cilium status
  ```

- [ ] Hubble enabled (if configured)
  ```bash
  kubectl get pods -n kube-system | grep hubble
  ```

- [ ] CoreDNS functional
  ```bash
  kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default
  ```

### Permissions

- [ ] Admin access working
  ```bash
  kubectl auth can-i '*' '*' --all-namespaces
  ```

- [ ] Node IAM role correct
  ```bash
  kubectl get configmap aws-auth -n kube-system -o yaml
  ```

## 📊 Resource Inventory

After deployment, you should have:

- [ ] 1 VPC
- [ ] 4 Subnets (2 public, 2 private)
- [ ] 2 NAT Gateways
- [ ] 2 Elastic IPs
- [ ] 3 Route Tables
- [ ] 1 Internet Gateway
- [ ] 2 Security Groups
- [ ] 1 EKS Cluster
- [ ] 2 IAM Roles
- [ ] 6+ IAM Policies
- [ ] 1 OIDC Provider
- [ ] 2 Launch Templates (per node group)
- [ ] 2 Auto Scaling Groups (per node group)
- [ ] 2+ EC2 Instances (depending on node group size)
- [ ] 2 Helm Releases (Cilium + CoreDNS)
- [ ] 1 aws-auth ConfigMap

Total: **~40-50 resources**

## 🚀 Next Steps

After successful deployment:

### Deploy Applications

- [ ] Deploy test application
  ```bash
  kubectl create deployment nginx --image=nginx
  kubectl expose deployment nginx --port=80 --type=LoadBalancer
  ```

- [ ] Verify LoadBalancer provisioning
  ```bash
  kubectl get services
  ```

### Setup Monitoring

- [ ] Deploy Prometheus (optional)
- [ ] Deploy Grafana (optional)
- [ ] Setup CloudWatch logging
- [ ] Configure alerts

### Security Hardening

- [ ] Review security groups
- [ ] Enable Pod Security Standards
- [ ] Setup Network Policies with Cilium
- [ ] Configure IRSA for workloads
- [ ] Enable audit logging

### Cost Optimization

- [ ] Review instance types
- [ ] Configure cluster autoscaler
- [ ] Setup Spot instances (if appropriate)
- [ ] Monitor costs in AWS Cost Explorer

## 🔧 Maintenance Tasks

### Regular Tasks

- [ ] Review Pulumi state regularly
  ```bash
  pulumi refresh
  ```

- [ ] Keep Kubernetes version up to date
  ```bash
  pulumi config set eks-pulumi:cluster_version 1.34
  pulumi up
  ```

- [ ] Update node AMIs periodically
  - Update AMI IDs in `node-groups.yaml`
  - Run `pulumi up`

- [ ] Review and rotate credentials

### Backup and Disaster Recovery

- [ ] Export Pulumi state
  ```bash
  pulumi stack export > stack-backup.json
  ```

- [ ] Backup important ConfigMaps and Secrets
  ```bash
  kubectl get configmap -A -o yaml > configmaps-backup.yaml
  kubectl get secret -A -o yaml > secrets-backup.yaml
  ```

- [ ] Document recovery procedures

## ❌ Decommissioning

When you need to destroy the infrastructure:

- [ ] Backup important data
- [ ] Export any necessary information
- [ ] Remove application workloads
  ```bash
  kubectl delete deployment --all --all-namespaces
  kubectl delete service --all --all-namespaces
  ```

- [ ] Destroy Pulumi stack
  ```bash
  pulumi destroy
  ```

- [ ] Verify all resources deleted
  ```bash
  pulumi stack
  ```

- [ ] Remove stack (optional)
  ```bash
  pulumi stack rm prod
  ```

## 📞 Support Resources

If you encounter issues:

- [ ] Check `PULUMI-README.md` for detailed documentation
- [ ] Review `TERRAFORM-PULUMI-COMPARISON.md` for migration info
- [ ] Check Pulumi documentation: https://www.pulumi.com/docs/
- [ ] Review AWS EKS documentation: https://docs.aws.amazon.com/eks/
- [ ] Check module code in `pulumi_modules/` for implementation details

## ✨ Success Criteria

Your deployment is successful when:

- ✅ All resources created without errors
- ✅ Nodes are in Ready state
- ✅ kubectl can access the cluster
- ✅ CoreDNS pods are running
- ✅ Cilium agents are running on all nodes
- ✅ Test workload can be deployed successfully
- ✅ Services can be exposed and accessed

---

**Congratulations! Your EKS cluster is ready for use! 🎉**

