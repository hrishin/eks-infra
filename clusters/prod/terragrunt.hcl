# Production environment configuration
include "root" {
  path = find_in_parent_folders()
}

# Production-specific inputs
inputs = {
  environment = "prod"
}

