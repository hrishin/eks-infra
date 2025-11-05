terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
}

# Data sources for cluster authentication
data "aws_eks_cluster_auth" "main" {
  name = var.cluster_name
}

# Create aws-auth ConfigMap for node bootstrap
resource "kubernetes_config_map" "aws_auth" {
  metadata {
    name      = "aws-auth"
    namespace = "kube-system"
  }

  data = {
    mapRoles = yamlencode(
      concat(
        # Node bootstrap role - allows nodes to join cluster
        [
          {
            rolearn  = var.node_role_arn
            username = "system:node:{{EC2PrivateDNSName}}"
            groups   = ["system:bootstrappers", "system:nodes"]
          }
        ],
        # Additional roles can be added here if needed
        []
      )
    )

    mapUsers = yamlencode(
      [
        # Cluster admin users via IAM ARN
        for arn in var.cluster_admin_user_arns : {
          userarn  = arn
          username = split("/", arn)[length(split("/", arn)) - 1]
          groups   = ["system:masters"]
        }
      ]
    )
  }

  depends_on = [
    data.aws_eks_cluster_auth.main
  ]
}