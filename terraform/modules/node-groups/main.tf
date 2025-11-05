terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Launch Template for each node group
resource "aws_launch_template" "node_group" {
  for_each = var.node_groups

  name_prefix = "${var.cluster_name}_${each.key}_"

  vpc_security_group_ids = concat(
    [var.cluster_security_group_id],
    [var.worker_node_security_group_id]
  )

  image_id = lookup(each.value, "ami_id", null)

  iam_instance_profile {
    name = var.node_instance_profile_name
  }

  instance_type = lookup(each.value, "instance_types", ["t3.medium"])[0]

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = lookup(each.value, "disk_size", 20)
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tags = merge(
    var.tags,
    {
      Name      = "${var.cluster_name}-${each.key}-node"
      NodeGroup = each.key
      "kubernetes.io/cluster/${var.cluster_name}" = "owned"
    }
  )

  lifecycle {
    create_before_destroy = true
  }

  user_data = base64encode(
    <<-EOT
    #!/bin/bash
    set -o xtrace
    LABELS="${join(",", [for lk, lv in lookup(local.node_groups_with_labels[each.key], "labels", {}) : "${lk}=${lv}"]) }"
    TAINTS="${join(",", [for t in lookup(var.node_groups[each.key], "taints", []) : "${t.key}=${lookup(t, "value", "")}:${t.effect}"]) }"
    KUBELET_ARGS=""
    if [ -n "$LABELS" ]; then
      KUBELET_ARGS="$KUBELET_ARGS --node-labels=$LABELS"
    fi
    if [ -n "$TAINTS" ]; then
      KUBELET_ARGS="$KUBELET_ARGS --register-with-taints=$TAINTS"
    fi
    /etc/eks/bootstrap.sh ${var.cluster_name} \
      --apiserver-endpoint '${var.cluster_endpoint}' \
      --b64-cluster-ca '${var.cluster_certificate_authority_data}' \
      --kubelet-extra-args "$KUBELET_ARGS"
    EOT
  )
}

# Convert Kubernetes taint effects to EKS format
locals {
  taint_effect_map = {
    "NoSchedule"        = "NO_SCHEDULE"
    "NoExecute"         = "NO_EXECUTE"
    "PreferNoSchedule"  = "PREFER_NO_SCHEDULE"
  }

  # Process node groups with taints
  node_groups_with_taints = {
    for k, v in var.node_groups : k => merge(
      v,
      {
        eks_taints = [
          for taint in lookup(v, "taints", []) : {
            key    = taint.key
            value  = lookup(taint, "value", "")
            effect = lookup(local.taint_effect_map, taint.effect, upper(taint.effect))
          }
        ]
      }
    )
  }

  # Detect GPU instances and add labels
  node_groups_with_labels = {
    for k, v in local.node_groups_with_taints : k => merge(
      v,
      {
        labels = merge(
          lookup(v, "labels", {}),
          length(regexall("^[pg]", join("", lookup(v, "instance_types", ["t3.medium"])))) > 0 ? {
            "accelerator"   = "nvidia-gpu"
            "nvidia.com/gpu" = "true"
            "gpu-type"      = length(regexall("^p3", join("", lookup(v, "instance_types", ["t3.medium"])))) > 0 ? "tesla-v100" : (
              length(regexall("^p4", join("", lookup(v, "instance_types", ["t3.medium"])))) > 0 ? "a100" : (
                length(regexall("^g4", join("", lookup(v, "instance_types", ["t3.medium"])))) > 0 ? "t4" : (
                  length(regexall("^g5", join("", lookup(v, "instance_types", ["t3.medium"])))) > 0 ? "a10g" : (
                    length(regexall("^g6", join("", lookup(v, "instance_types", ["t3.medium"])))) > 0 ? "l4" : "unknown"
                  )
                )
              )
            )
          } : {}
        )
      }
    )
  }
}

resource "aws_autoscaling_group" "node_group" {
  for_each = var.node_groups

  name                = "${var.cluster_name}-${each.key}"
  vpc_zone_identifier = var.private_subnet_ids

  desired_capacity = lookup(each.value, "desired_size", 1)
  max_size         = lookup(each.value, "max_size", 3)
  min_size         = lookup(each.value, "min_size", 1)

  launch_template {
    id      = aws_launch_template.node_group[each.key].id
    version = aws_launch_template.node_group[each.key].latest_version
  }

  health_check_type         = "EC2"
  health_check_grace_period = 300
  termination_policies      = ["OldestInstance"]

  tag {
    key                 = "Name"
    value               = "${var.cluster_name}-${each.key}-node"
    propagate_at_launch = true
  }

  tag {
    key                 = "NodeGroup"
    value               = each.key
    propagate_at_launch = true
  }

  tag {
    key                 = "kubernetes.io/cluster/${var.cluster_name}"
    value               = "owned"
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = var.tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  depends_on = [
    aws_launch_template.node_group
  ]
}


