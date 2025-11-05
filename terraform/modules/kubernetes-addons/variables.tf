variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  type        = string
}

variable "cluster_ca_certificate" {
  description = "Base64 encoded certificate data for the cluster"
  type        = string
}

variable "enable_cilium" {
  description = "Enable Cilium CNI"
  type        = bool
  default     = true
}

variable "enable_coredns" {
  description = "Enable CoreDNS"
  type        = bool
  default     = true
}

variable "pod_cidr_range" {
  description = "CIDR range for pods"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_role_arn" {
  description = "node role ARN"
  type = string
  default = ""
}

variable "cluster_admin_user_arns" {
  description = "List of IAM user ARNs to grant cluster-admin (system:masters) via EKS Access Entries"
  type        = list(string)
  default     = []
}