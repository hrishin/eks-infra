variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "node_groups" {
  description = "Map of node group configurations"
  type = map(object({
    instance_types = list(string)
    desired_size   = number
    min_size       = number
    max_size       = number
    disk_size      = optional(number, 20)
    ami_id         = optional(string)
    ami_type       = optional(string)
    labels         = optional(map(string), {})
    taints = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
  }))
  default = {}
}

variable "node_group_service_role_arn" {
  description = "IAM role ARN for EKS node groups"
  type        = string
}

variable "node_instance_profile_name" {
  description = "IAM instance profile name for EC2 worker nodes"
  type        = string
}

variable "cluster_security_group_id" {
  description = "Security group ID of the EKS cluster"
  type        = string
}

variable "worker_node_security_group_id" {
  description = "Security group ID for worker nodes"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "cluster_endpoint" {
  description = "EKS API server endpoint for bootstrap"
  type        = string
}

variable "cluster_certificate_authority_data" {
  description = "Base64-encoded EKS cluster CA data for bootstrap"
  type        = string
}

variable "tags" {
  description = "A map of tags to assign to the resource"
  type        = map(string)
  default     = {}
}

