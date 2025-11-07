"""
EKS Cluster Infrastructure with Pulumi
Converted from Terraform/Terragrunt setup

This is the main entry point that orchestrates all modules.
"""

import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
from typing import List
import yaml

from pulumi_modules.shared.config import get_pulumi_config, load_node_groups_config
from pulumi_modules.networking.networking import create_networking
from pulumi_modules.eks_cluster.cluster import create_eks_cluster
from pulumi_modules.node_groups.node_groups import create_node_groups
from pulumi_modules.eks_auth.auth import create_eks_auth
from pulumi_modules.kubernetes_addons.addons import create_kubernetes_addons

def main():
    """
    Main function to orchestrate EKS cluster creation
    """
    
    # Load configuration
    config_data = get_pulumi_config()
    
    # Load node groups configuration from YAML
    node_groups_config = load_node_groups_config()
    
    # Create tags
    tags = {
        "Environment": config_data["environment"],
        "ManagedBy": "pulumi",
        "Project": config_data["project"],
    }
    
    # 1. Create Networking Infrastructure
    pulumi.log.info("Creating networking infrastructure...")
    networking = create_networking(
        cluster_name=config_data["cluster_name"],
        vpc_cidr=config_data["vpc_cidr"],
        availability_zones=config_data["availability_zones"],
        tags=tags,
    )
    
    # 2. Create EKS Cluster
    pulumi.log.info("Creating EKS cluster...")
    cluster = create_eks_cluster(
        cluster_name=config_data["cluster_name"],
        cluster_version=config_data["cluster_version"],
        public_subnet_ids=networking["public_subnet_ids"],
        private_subnet_ids=networking["private_subnet_ids"],
        cluster_admin_user_arns=config_data["cluster_admin_user_arns"],
        tags=tags,
    )
    
    # Update the networking security group to allow traffic from cluster
    # This must be done after cluster is created
    def update_worker_sg(cluster_sg_id):
        if cluster_sg_id:
            return aws.ec2.SecurityGroupRule(
                "worker-from-cluster",
                type="ingress",
                from_port=0,
                to_port=0,
                protocol="-1",
                source_security_group_id=cluster_sg_id,
                security_group_id=networking["worker_node_security_group_id"],
                description="All traffic from EKS cluster",
                opts=pulumi.ResourceOptions(
                    depends_on=[cluster["cluster"]],
                ),
            )
    
    # Apply the security group rule
    cluster["cluster_security_group_id"].apply(update_worker_sg)
    
    # 3. Create Node Groups
    pulumi.log.info("Creating node groups...")
    node_groups = create_node_groups(
        cluster_name=config_data["cluster_name"],
        node_groups=node_groups_config,
        node_group_service_role_arn=cluster["node_group_service_role_arn"],
        node_instance_profile_name=cluster["node_instance_profile_name"],
        cluster_security_group_id=cluster["cluster_security_group_id"],
        worker_node_security_group_id=networking["worker_node_security_group_id"],
        private_subnet_ids=networking["private_subnet_ids"],
        cluster_endpoint=cluster["cluster_endpoint"],
        cluster_ca_data=cluster["cluster_certificate_authority_data"],
        tags=tags,
    )
    
    # 4. Configure EKS Authentication (aws-auth ConfigMap)
    pulumi.log.info("Configuring EKS authentication...")
    eks_auth = create_eks_auth(
        cluster_name=config_data["cluster_name"],
        cluster_endpoint=cluster["cluster_endpoint"],
        cluster_ca_certificate=cluster["cluster_certificate_authority_data"],
        node_role_arn=cluster["node_group_service_role_arn"],
        cluster_admin_user_arns=config_data["cluster_admin_user_arns"],
        cluster=cluster["cluster"],
        region=config_data["region"],
    )
    
    # 5. Install Kubernetes Add-ons (Cilium CNI and CoreDNS)
    pulumi.log.info("Installing Kubernetes add-ons...")
    addons = create_kubernetes_addons(
        cluster_name=config_data["cluster_name"],
        cluster_endpoint=cluster["cluster_endpoint"],
        cluster_ca_certificate=cluster["cluster_certificate_authority_data"],
        pod_cidr_range=config_data["pod_cidr_range"],
        enable_cilium=config_data["enable_cilium"],
        enable_coredns=config_data["enable_coredns"],
        cluster=cluster["cluster"],
        aws_auth_configmap=eks_auth["aws_auth_configmap"],
        region=config_data["region"],
    )
    
    # Export outputs
    pulumi.export("cluster_name", cluster["cluster"].name)
    pulumi.export("cluster_endpoint", cluster["cluster_endpoint"])
    pulumi.export("cluster_security_group_id", cluster["cluster_security_group_id"])
    pulumi.export("cluster_arn", cluster["cluster"].arn)
    pulumi.export("cluster_oidc_issuer_url", cluster["cluster_oidc_issuer_url"])
    pulumi.export("cluster_oidc_provider_arn", cluster["cluster_oidc_provider_arn"])
    pulumi.export("node_group_service_role_arn", cluster["node_group_service_role_arn"])
    pulumi.export("node_instance_profile_name", cluster["node_instance_profile_name"])
    pulumi.export("vpc_id", networking["vpc_id"])
    pulumi.export("public_subnet_ids", networking["public_subnet_ids"])
    pulumi.export("private_subnet_ids", networking["private_subnet_ids"])
    pulumi.export("worker_node_security_group_id", networking["worker_node_security_group_id"])
    pulumi.export("autoscaling_group_names", node_groups["autoscaling_group_names"])
    pulumi.export("launch_template_ids", node_groups["launch_template_ids"])
    
    # Export kubeconfig
    def create_kubeconfig(endpoint, ca_data, cluster_name):
        return pulumi.Output.all(endpoint, ca_data, cluster_name).apply(
            lambda args: f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {args[1]}
    server: {args[0]}
  name: {args[2]}
contexts:
- context:
    cluster: {args[2]}
    user: {args[2]}
  name: {args[2]}
current-context: {args[2]}
kind: Config
preferences: {{}}
users:
- name: {args[2]}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
        - eks
        - get-token
        - --cluster-name
        - {args[2]}
        - --region
        - {config_data['region']}
"""
        )
    
    kubeconfig = create_kubeconfig(
        cluster["cluster_endpoint"],
        cluster["cluster_certificate_authority_data"],
        config_data["cluster_name"]
    )
    pulumi.export("kubeconfig", kubeconfig)
    
    # Export Helm release names
    if addons.get("cilium_release"):
        pulumi.export("cilium_release_name", addons["cilium_release"].name)
    if addons.get("coredns_release"):
        pulumi.export("coredns_release_name", addons["coredns_release"].name)

# Run the main function
main()

