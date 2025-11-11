"""
Configuration loading utilities for Pulumi
"""

import pulumi
import yaml
from typing import Dict, Any, List


def get_pulumi_config() -> Dict[str, Any]:
    """
    Load and process Pulumi configuration
    
    Returns:
        Dictionary containing all configuration values
    """
    config = pulumi.Config()
    aws_config = pulumi.Config("aws")
    
    # Get region from AWS config (fallback to AWS CLI default or eu-west-2)
    region = aws_config.get("region")
    if not region:
        # Try to get from environment or default
        import os
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-west-2"
    
    # Get cluster configuration
    cluster_name = config.get("cluster_name") or "infra-cluster"
    cluster_version = config.get("cluster_version") or "1.33"
    
    # Get networking configuration
    vpc_cidr = config.get("vpc_cidr") or "10.0.0.0/16"
    pod_cidr_range = config.get("pod_cidr_range") or "10.0.0.0/16"
    
    # Get availability zones (comma-separated string)
    az_string = config.get("availability_zones") or "eu-west-2a,eu-west-2c"
    availability_zones = [az.strip() for az in az_string.split(",") if az.strip()]
    
    # Get cluster admin user ARNs (comma-separated string)
    admin_arns_string = config.get("cluster_admin_user_arns") or ""
    cluster_admin_user_arns = [arn.strip() for arn in admin_arns_string.split(",") if arn.strip()]
    
    # Get addon configuration
    enable_cilium = config.get_bool("enable_cilium")
    if enable_cilium is None:
        enable_cilium = True
    
    enable_coredns = config.get_bool("enable_coredns")
    if enable_coredns is None:
        enable_coredns = True

    enable_flux = config.get_bool("enable_flux")
    if enable_flux is None:
        enable_flux = True
    
    # Get environment and project tags
    environment = config.get("environment") or "production"
    project = config.get("project") or "eks-cluster"
    
    return {
        "region": region,
        "cluster_name": cluster_name,
        "cluster_version": cluster_version,
        "vpc_cidr": vpc_cidr,
        "pod_cidr_range": pod_cidr_range,
        "availability_zones": availability_zones,
        "cluster_admin_user_arns": cluster_admin_user_arns,
        "enable_cilium": enable_cilium,
        "enable_coredns": enable_coredns,
        "enable_flux": enable_flux,
        "environment": environment,
        "project": project,
    }


def load_node_groups_config(file_path: str = "node-groups.yaml") -> Dict[str, Any]:
    """
    Load node groups configuration from YAML file
    
    Args:
        file_path: Path to the node groups configuration file
        
    Returns:
        Dictionary containing node groups configuration
    """
    try:
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get("node_groups", {})
    except FileNotFoundError:
        pulumi.log.warn(f"Node groups config file {file_path} not found. Using empty configuration.")
        return {}
    except Exception as e:
        pulumi.log.warn(f"Error loading node groups config: {e}. Using empty configuration.")
        return {}

