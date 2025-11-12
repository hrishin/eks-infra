"""
EKS Authentication configuration (aws-auth ConfigMap)
Equivalent to terraform/modules/eks-auth
"""

import base64

import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
from typing import List, Any
import yaml as yaml_lib


def create_eks_auth(
    cluster_name: str,
    cluster_endpoint: pulumi.Output,
    cluster_ca_certificate: pulumi.Output,
    node_role_arn: pulumi.Output,
    cluster_admin_user_arns: List[str],
    cluster: Any,
    region: str,
) -> dict:
    """
    Create aws-auth ConfigMap for EKS cluster authentication
    
    Args:
        cluster_name: Name of the EKS cluster
        cluster_endpoint: Cluster endpoint URL
        cluster_ca_certificate: Base64-encoded cluster CA certificate
        node_role_arn: IAM role ARN for worker nodes
        cluster_admin_user_arns: List of IAM user ARNs for cluster admins
        cluster: EKS cluster resource (for dependency)
        region: AWS region where the cluster lives
        
    Returns:
        Dictionary containing auth resources
    """
    
    # Create Kubernetes provider
    k8s_provider = k8s.Provider(
        f"{cluster_name}-k8s-provider",
        kubeconfig=pulumi.Output.all(
            cluster_endpoint,
            cluster_ca_certificate,
        ).apply(lambda args: f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {args[1]}
    server: {args[0]}
  name: {cluster_name}
contexts:
- context:
    cluster: {cluster_name}
    user: {cluster_name}
  name: {cluster_name}
current-context: {cluster_name}
kind: Config
preferences: {{}}
users:
- name: {cluster_name}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
        - eks
        - get-token
        - --cluster-name
        - {cluster_name}
        - --region
        - {region}
"""),
        opts=pulumi.ResourceOptions(depends_on=[cluster]),
    )
    
    # Create aws-auth ConfigMap data
    def create_aws_auth_data(node_role):
        map_roles = [
            {
                "rolearn": node_role,
                "username": "system:node:{{EC2PrivateDNSName}}",
                "groups": ["system:bootstrappers", "system:nodes"]
            }
        ]
        
        map_users = [
            {
                "userarn": arn,
                "username": arn.split("/")[-1],
                "groups": ["system:masters"]
            }
            for arn in cluster_admin_user_arns
        ]
        
        return {
            "mapRoles": yaml_lib.dump(map_roles, default_flow_style=False),
            "mapUsers": yaml_lib.dump(map_users, default_flow_style=False),
        }
    
    aws_auth_data = node_role_arn.apply(create_aws_auth_data)
    
    # Create aws-auth ConfigMap
    aws_auth_configmap = k8s.core.v1.ConfigMap(
        "aws-auth",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="aws-auth",
            namespace="kube-system",
        ),
        data=aws_auth_data,
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[cluster],
        ),
    )
    
    return {
        "aws_auth_configmap": aws_auth_configmap,
        "k8s_provider": k8s_provider,
    }

