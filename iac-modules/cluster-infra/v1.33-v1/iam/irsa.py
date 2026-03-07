import json
import os
from typing import Dict, Any

import pulumi
import pulumi_aws as aws


def create_aws_lbc_irsa(
    cluster_name: str,
    oidc_issuer_url: pulumi.Output,
    oidc_provider_arn: pulumi.Output,
    tags: Dict[str, str],
) -> Dict[str, Any]:
    """
    Create IRSA (IAM Role for Service Accounts) for AWS Load Balancer Controller
    """

    # Parse the downloaded IAM policy and create an AWS IAM Policy
    policy_file_path = os.path.join(os.path.dirname(__file__), "aws_lbc_iam_policy.json")
    with open(policy_file_path, "r") as f:
        policy_document = f.read()

    aws_lbc_policy = aws.iam.Policy(
        f"{cluster_name}-aws-lbc-policy",
        name=f"{cluster_name}-aws-load-balancer-controller",
        policy=policy_document,
        tags=tags,
    )

    # The service account namespace and name as deployed by the Helm chart
    sa_namespace = "aws-load-balancer-controller"
    sa_name = "aws-load-balancer-controller"

    # Construct the trust policy using the OIDC provider
    assume_role_policy = pulumi.Output.all(oidc_issuer_url, oidc_provider_arn).apply(
        lambda args: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Federated": args[1]
                    },
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Condition": {
                        "StringEquals": {
                            f"{args[0].replace('https://', '')}:sub": f"system:serviceaccount:{sa_namespace}:{sa_name}",
                            f"{args[0].replace('https://', '')}:aud": "sts.amazonaws.com"
                        }
                    }
                }
            ]
        })
    )

    aws_lbc_role = aws.iam.Role(
        f"{cluster_name}-aws-lbc-role",
        name=f"{cluster_name}-aws-load-balancer-controller",
        assume_role_policy=assume_role_policy,
        tags=tags,
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-aws-lbc-role-policy-attachment",
        role=aws_lbc_role.name,
        policy_arn=aws_lbc_policy.arn,
    )

    return {
        "role_arn": aws_lbc_role.arn,
        "role_name": aws_lbc_role.name,
    }
