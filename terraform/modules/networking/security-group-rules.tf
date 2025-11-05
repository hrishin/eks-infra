# Security group rule to allow traffic from EKS cluster to worker nodes
# This is a separate resource to handle updates after cluster creation
resource "aws_security_group_rule" "worker_from_cluster" {
  count = var.cluster_security_group_id != "" ? 1 : 0

  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = var.cluster_security_group_id
  security_group_id        = aws_security_group.worker_nodes.id
  description              = "All traffic from EKS cluster"

  lifecycle {
    create_before_destroy = true
  }
}

