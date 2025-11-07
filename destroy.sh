#!/bin/bash

# EKS Cluster Destruction Script
# This script destroys the EKS cluster infrastructure using Terragrunt

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${SCRIPT_DIR}/clusters/prod"

echo "⚠️  WARNING: This will destroy all EKS cluster infrastructure!"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Destruction cancelled"
    exit 1
fi

echo ""
echo "🗑️  Starting infrastructure destruction..."
echo ""

# # Destroy modules in reverse order
# echo "5️⃣  Destroying Kubernetes add-ons..."
# cd "${ENV_DIR}/kubernetes-addons"
# terragrunt destroy -auto-approve

echo ""
echo "4️⃣  Destroying node groups..."
cd "${ENV_DIR}/node-groups"
terragrunt destroy -auto-approve

echo ""
echo "3️⃣  Destroying EKS cluster..."
cd "${ENV_DIR}/eks-cluster"
terragrunt destroy -auto-approve

echo ""
echo "2️⃣  Destroying networking..."
cd "${ENV_DIR}/networking"
terragrunt destroy -auto-approve

echo ""
echo "✅ Destruction complete!"

