#!/bin/bash
# Setup script for Pulumi EKS infrastructure

set -e

echo "Setting up Pulumi EKS infrastructure..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check if Pulumi is installed
if ! command -v pulumi &> /dev/null; then
    echo "Error: Pulumi is not installed."
    echo "Please install Pulumi: curl -fsSL https://get.pulumi.com | sh"
    exit 1
fi

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Login to Pulumi: pulumi login"
echo "3. Create a new stack: pulumi stack init dev"
echo "4. Configure the stack (optional, defaults are set in Pulumi.yaml):"
echo "   pulumi config set aws:region eu-west-2"
echo "   pulumi config set eks-pulumi:cluster_name infra-cluster"
echo "5. Preview changes: pulumi preview"
echo "6. Deploy infrastructure: pulumi up"
echo ""

