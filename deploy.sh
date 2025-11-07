#!/bin/bash

# EKS Cluster Deployment Script
# This script deploys the EKS cluster infrastructure using Terragrunt

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_DIR="${SCRIPT_DIR}/clusters/prod"

skip_step=${1:-""}

echo "🚀 Starting EKS cluster deployment..."
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed. Please install Terraform >= 1.0"
    exit 1
fi

if ! command -v terragrunt &> /dev/null; then
    echo "❌ Terragrunt is not installed. Please install Terragrunt >= 0.40"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install AWS CLI"
    exit 1
fi

echo "✅ All prerequisites met"
echo ""

# Deploy modules in order
echo "📦 Deploying infrastructure modules..."
echo ""

if [ "$skip_step" != "networking" ]; then
    echo "1️⃣  Deploying networking..."
    cd "${CLUSTER_DIR}/networking"
    terragrunt apply -auto-approve
else
    echo "Skipping networking deployment"
fi

echo ""
if [ "$skip_step" != "eks-cluster" ]; then
    echo "2️⃣  Deploying EKS cluster..."
    cd "${CLUSTER_DIR}/eks-cluster"
    terragrunt apply -auto-approve
else
    echo "Skipping EKS cluster deployment"
fi

echo ""
if [ "$skip_step" != "networking" ]; then
    echo "3️⃣  Updating networking with cluster security group..."
    cd "${CLUSTER_DIR}/networking"
    terragrunt apply -auto-approve
else
    echo "Skipping node groups deployment"
fi

# echo ""
# if [ "$skip_step" != "auth" ]; then
#     echo "3️⃣  Updating auth to enable cluster access..."
#     cd "${CLUSTER_DIR}/eks-auth"
#     terragrunt apply -auto-approve
# else
#     echo "Skipping auth deployment"
# fi

echo ""
if [ "$skip_step" != "node-groups" ]; then
    echo "4️⃣  Deploying node groups..."
    cd "${CLUSTER_DIR}/node-groups"
    terragrunt apply -auto-approve
else
    echo "Skipping node groups deployment"
fi

echo ""
if [ "$skip_step" != "addons" ]; then
    echo "5️⃣  Deploying Kubernetes add-ons..."
    cd "${CLUSTER_DIR}/kubernetes-addons"
    terragrunt apply -auto-approve
else
    echo "Skipping Kubernetes add-ons deployment"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Configure kubectl: aws eks update-kubeconfig --name infra-cluster --region eu-west-2"
echo "   2. Verify cluster: kubectl get nodes"
echo "   3. Check pods: kubectl get pods -A"

