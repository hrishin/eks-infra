"""
EKS Node Groups infrastructure
Equivalent to terraform/modules/node-groups
"""

import base64
import time
from typing import Any, Dict, List, Optional, Tuple

import pulumi
import pulumi_aws as aws


class WaitForAsgReady(pulumi.ComponentResource):
    ready: pulumi.Output[bool]

    def __init__(
        self,
        name: str,
        asg_name: pulumi.Input[str],
        region: pulumi.Input[str],
        timeout_seconds: int = 900,
        poll_interval_seconds: int = 15,
        opts: Optional[pulumi.ResourceOptions] = None,
    ) -> None:
        super().__init__("custom:autoscaling:WaitForAsgReady", name, None, opts)

        readiness_details = pulumi.Output.all(
            asg_name, region, timeout_seconds, poll_interval_seconds
        ).apply(self._wait_for_asg_ready)

        self.ready = readiness_details.apply(lambda _: True)
        self.details = readiness_details

        self.register_outputs(
            {
                "ready": self.ready,
                "details": self.details,
            }
        )

    def _wait_for_asg_ready(self, args: Tuple[str, str, int, int]) -> Dict[str, Any]:
        asg_name, region, timeout_seconds, poll_interval_seconds = args

        if pulumi.runtime.is_dry_run():
            pulumi.log.info(
                f"Preview: skipping Auto Scaling Group readiness check for {asg_name or '<unknown>'}."
            )
            return {
                "asg_name": asg_name,
                "desired_capacity": 0,
                "healthy_instances": 0,
            }

        import boto3
        from botocore.exceptions import ClientError  # type: ignore

        client = boto3.client("autoscaling", region_name=region)
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                response = client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
            except ClientError as exc:
                pulumi.log.warn(f"Failed to describe Auto Scaling Group {asg_name}: {exc}")
                time.sleep(poll_interval_seconds)
                continue

            groups = response.get("AutoScalingGroups") or []
            if not groups:
                pulumi.log.warn(f"Auto Scaling Group {asg_name} not found; retrying...")
                time.sleep(poll_interval_seconds)
                continue

            group = groups[0]
            desired_capacity = group.get("DesiredCapacity", 0)
            instances = group.get("Instances") or []
            pulumi.log.info(f"Auto Scaling Group {asg_name} has {desired_capacity} desired capacity and {len(instances)} instances.")
            for instance in instances:
                pulumi.log.info(f"Instance {instance.get('InstanceId')} is {instance.get('LifecycleState')} and {instance.get('HealthStatus')}.")
            healthy_instances = sum(
                1
                for instance in instances
                if instance.get("LifecycleState") == "InService" and instance.get("HealthStatus") == "Healthy"
            )

            if desired_capacity == 0 or healthy_instances >= desired_capacity:
                pulumi.log.info(
                    f"Auto Scaling Group {asg_name} is healthy ({healthy_instances}/{desired_capacity} instances InService)."
                )
                return {
                    "asg_name": asg_name,
                    "desired_capacity": desired_capacity,
                    "healthy_instances": healthy_instances,
                }
            pulumi.log.info(f"Auto Scaling Group {asg_name} is not healthy ({healthy_instances}/{desired_capacity} instances InService). Retrying...")
            time.sleep(poll_interval_seconds)

        raise Exception(
            f"Timed out after {timeout_seconds}s waiting for Auto Scaling Group {asg_name} to become healthy."
        )

def create_node_groups(
    cluster_name: str,
    node_groups: Dict[str, Any],
    node_group_service_role_arn: pulumi.Output,
    node_instance_profile_name: pulumi.Output,
    cluster_security_group_id: pulumi.Output,
    worker_node_security_group_id: pulumi.Output,
    private_subnet_ids: List[pulumi.Output],
    cluster_endpoint: pulumi.Output,
    cluster_ca_data: pulumi.Output,
    tags: Dict[str, str],
    region: str,
    dns_cluster_ip: Optional[pulumi.Input[str]] = None,
) -> Dict[str, Any]:
    """
    Create self-managed node groups with launch templates and auto-scaling groups
    
    Args:
        cluster_name: Name of the EKS cluster
        node_groups: Node groups configuration from YAML
        node_group_service_role_arn: IAM role ARN for node groups
        node_instance_profile_name: Instance profile name
        cluster_security_group_id: Cluster security group ID
        worker_node_security_group_id: Worker node security group ID
        private_subnet_ids: List of private subnet IDs
        cluster_endpoint: EKS cluster endpoint
        cluster_ca_data: Cluster CA certificate data
        tags: Common tags to apply to resources
        region: AWS region where the Auto Scaling Groups are created
        dns_cluster_ip: Cluster IP address for CoreDNS service to pass to bootstrap
        
    Returns:
        Dictionary containing node group resource outputs
    """
    
    # Taint effect mapping
    taint_effect_map = {
        "NoSchedule": "NO_SCHEDULE",
        "NoExecute": "NO_EXECUTE",
        "PreferNoSchedule": "PREFER_NO_SCHEDULE",
    }
    
    # Detect GPU type based on instance type
    def detect_gpu_type(instance_types: List[str]) -> Dict[str, str]:
        """Detect GPU type from instance type"""
        instance_type = instance_types[0] if instance_types else ""
        
        if instance_type.startswith("p3"):
            return {"accelerator": "nvidia-gpu", "nvidia.com/gpu": "true", "gpu-type": "tesla-v100"}
        elif instance_type.startswith("p4"):
            return {"accelerator": "nvidia-gpu", "nvidia.com/gpu": "true", "gpu-type": "a100"}
        elif instance_type.startswith("g4"):
            return {"accelerator": "nvidia-gpu", "nvidia.com/gpu": "true", "gpu-type": "t4"}
        elif instance_type.startswith("g5"):
            return {"accelerator": "nvidia-gpu", "nvidia.com/gpu": "true", "gpu-type": "a10g"}
        elif instance_type.startswith("g6"):
            return {"accelerator": "nvidia-gpu", "nvidia.com/gpu": "true", "gpu-type": "l4"}
        else:
            return {}
    
    # Get all private subnet details for AZ filtering
    subnet_details = {}
    for subnet_id in private_subnet_ids:
        # We'll filter subnets later based on AZ requirements
        pass
    
    launch_templates: Dict[str, aws.ec2.LaunchTemplate] = {}
    autoscaling_groups: Dict[str, aws.autoscaling.Group] = {}
    asg_readiness_checks: Dict[str, WaitForAsgReady] = {}
    
    for ng_name, ng_config in node_groups.items():
        pulumi.log.info("Creating node group infrastructure...")
        pulumi.log.info(f"Node group name: {ng_name}")
        pulumi.log.info(f"Node group config: {ng_config}")
        
        # Process labels
        base_labels = ng_config.get("labels", {})
        gpu_labels = detect_gpu_type(ng_config.get("instance_types", ["t3.medium"]))
        all_labels = {**base_labels, **gpu_labels}
        
        # Process taints
        taints = ng_config.get("taints", [])
        
        # Create user data script
        def create_user_data(endpoint: str, ca_data: str, labels: Dict[str, str], taints_list: List[Dict[str, str]], dns_ip: Optional[str]) -> str:
            labels_str = ",".join([f"{k}={v}" for k, v in labels.items()])
            taints_str = ",".join([
                f"{t['key']}={t.get('value', '')}:{t['effect']}"
                for t in taints_list
            ])
            
            kubelet_args = ""
            if labels_str:
                kubelet_args += f" --node-labels={labels_str}"
            if taints_str:
                kubelet_args += f" --register-with-taints={taints_str}"
            
            lines = [
                "#!/bin/bash",
                "set -o xtrace",
                f"/etc/eks/bootstrap.sh {cluster_name} \\",
                f"  --apiserver-endpoint '{endpoint}' \\",
                f"  --b64-cluster-ca '{ca_data}' \\",
            ]
            if dns_ip:
                lines.append(f"  --dns-cluster-ip '{dns_ip}' \\")
            lines.append(f'  --kubelet-extra-args "{kubelet_args}"')
            return "\n".join(lines) + "\n"
        
        if dns_cluster_ip is not None:
            user_data = pulumi.Output.all(cluster_endpoint, cluster_ca_data, all_labels, taints, dns_cluster_ip).apply(
                lambda args: base64.b64encode(create_user_data(args[0], args[1], args[2], args[3], args[4]).encode()).decode()
            )
        else:
            user_data = pulumi.Output.all(cluster_endpoint, cluster_ca_data, all_labels, taints).apply(
                lambda args: base64.b64encode(create_user_data(args[0], args[1], args[2], args[3], None).encode()).decode()
            )
        
        # Combine security groups
        security_group_ids = pulumi.Output.all(
            cluster_security_group_id,
            worker_node_security_group_id
        ).apply(lambda args: [args[0], args[1]])
        
        # Create Launch Template
        lt = aws.ec2.LaunchTemplate(
            f"{cluster_name}_{ng_name}_lt",
            name_prefix=f"{cluster_name}_{ng_name}_",
            vpc_security_group_ids=security_group_ids,
            image_id=ng_config.get("ami_id"),
            iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
                name=node_instance_profile_name,
            ),
            instance_type=ng_config.get("instance_types", ["t3.medium"])[0],
            block_device_mappings=[
                aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
                    device_name="/dev/xvda",
                    ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                        volume_size=ng_config.get("disk_size", 20),
                        volume_type="gp3",
                        delete_on_termination=True,
                    ),
                ),
            ],
            metadata_options=aws.ec2.LaunchTemplateMetadataOptionsArgs(
                http_endpoint="enabled",
                http_tokens="required",
                http_put_response_hop_limit=2,
            ),
            placement=aws.ec2.LaunchTemplatePlacementArgs(
                tenancy=ng_config.get("tenancy")
            ) if ng_config.get("tenancy") else None,
            user_data=user_data,
            tag_specifications=[
                aws.ec2.LaunchTemplateTagSpecificationArgs(
                    resource_type="instance",
                    tags={
                        **tags,
                        "Name": f"{cluster_name}-{ng_name}-node",
                        "NodeGroup": ng_name,
                        f"kubernetes.io/cluster/{cluster_name}": "owned",
                    },
                ),
                aws.ec2.LaunchTemplateTagSpecificationArgs(
                    resource_type="volume",
                    tags={
                        **tags,
                        "Name": f"{cluster_name}-{ng_name}-volume",
                        "NodeGroup": ng_name,
                    },
                ),
            ],
        )
        
        launch_templates[ng_name] = lt
        
        # Determine subnets for this node group
        # If availability_zones is specified, filter subnets
        # For now, we'll use all private subnets
        # In production, you'd need to filter based on AZ
        ng_subnet_ids = private_subnet_ids
        
        # If availability_zones is specified in config, we need to filter
        # This would require looking up subnet AZs, which we'll handle with Output.all
        if ng_config.get("availability_zones"):
            # For simplicity, using all subnets. In production, filter by AZ
            pass
        
        refresh_triggers = [
            trigger
            for trigger in ng_config.get("refresh_triggers", [])
            if trigger != "launch_template"
        ]

        # Create Auto Scaling Group
        asg = aws.autoscaling.Group(
            f"{cluster_name}-{ng_name}-asg",
            name=f"{cluster_name}-{ng_name}",
            vpc_zone_identifiers=ng_subnet_ids,
            desired_capacity=ng_config.get("desired_size", 1),
            max_size=ng_config.get("max_size", 3),
            min_size=ng_config.get("min_size", 1),
            launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
                id=lt.id,
                version="$Latest",
            ),
            instance_refresh=aws.autoscaling.GroupInstanceRefreshArgs(
                strategy="Rolling",
                preferences=aws.autoscaling.GroupInstanceRefreshPreferencesArgs(
                    min_healthy_percentage=ng_config.get("refresh_min_healthy_percent", 90),
                    skip_matching=ng_config.get("refresh_skip_matching", True),
                ),
                triggers=refresh_triggers or None,
            ),
            health_check_type="EC2",
            health_check_grace_period=300,
            termination_policies=["OldestInstance"],
            tags=[
                aws.autoscaling.GroupTagArgs(
                    key="Name",
                    value=f"{cluster_name}-{ng_name}-node",
                    propagate_at_launch=True,
                ),
                aws.autoscaling.GroupTagArgs(
                    key="NodeGroup",
                    value=ng_name,
                    propagate_at_launch=True,
                ),
                aws.autoscaling.GroupTagArgs(
                    key=f"kubernetes.io/cluster/{cluster_name}",
                    value="owned",
                    propagate_at_launch=True,
                ),
            ] + [
                aws.autoscaling.GroupTagArgs(
                    key=k,
                    value=v,
                    propagate_at_launch=True,
                )
                for k, v in tags.items()
            ],
            opts=pulumi.ResourceOptions(depends_on=[lt]),
        )
        
        autoscaling_groups[ng_name] = asg

        readiness_timeout = ng_config.get("readiness_timeout_seconds", 900)
        readiness_poll_interval = ng_config.get("readiness_poll_interval_seconds", 15)

        asg_ready = WaitForAsgReady(
            f"{cluster_name}-{ng_name}-asg-ready",
            asg_name=asg.name,
            region=region,
            timeout_seconds=readiness_timeout,
            poll_interval_seconds=readiness_poll_interval,
            opts=pulumi.ResourceOptions(depends_on=[asg]),
        )
        asg_readiness_checks[ng_name] = asg_ready
    
    return {
        "autoscaling_group_names": {k: v.name for k, v in autoscaling_groups.items()},
        "launch_template_ids": {k: v.id for k, v in launch_templates.items()},
        "autoscaling_group_readiness": asg_readiness_checks,
    }

