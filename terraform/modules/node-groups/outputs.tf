output "autoscaling_group_names" {
  description = "Names of the self-managed Auto Scaling Groups"
  value       = { for k, v in aws_autoscaling_group.node_group : k => v.name }
}

output "launch_template_ids" {
  description = "IDs of the launch templates for node groups"
  value       = { for k, v in aws_launch_template.node_group : k => v.id }
}

