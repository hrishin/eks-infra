variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version to use for the EKS cluster"
  type        = string
  default     = "1.32"
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "tags" {
  description = "A map of tags to assign to the resource"
  type        = map(string)
  default     = {}
}

variable "cluster_authentication_mode" {
  description = "EKS cluster authentication mode for access entries/policies (API or API_AND_CONFIG_MAP)"
  type        = string
  default     = "API_AND_CONFIG_MAP"
  validation {
    condition     = contains(["API", "API_AND_CONFIG_MAP"], var.cluster_authentication_mode)
    error_message = "cluster_authentication_mode must be one of: API, API_AND_CONFIG_MAP."
  }
}

variable "cluster_admin_user_arns" {
  description = "List of IAM user ARNs to grant cluster-admin (system:masters)"
  type        = list(string)
  default     = []
}
