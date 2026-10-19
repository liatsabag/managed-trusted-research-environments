/**
 * Variables for Spoke Research Room Module
 * GCP Health Data Platform POC
 */

variable "room_id" {
  description = "Unique identifier for the research room (e.g., rr-oncology-01)"
  type        = string
}

variable "room_name" {
  description = "Human-readable descriptive name of the research room"
  type        = string
}

variable "institute_id" {
  description = "Identifier of the sponsoring institution"
  type        = string
}

variable "spoke_project_id" {
  description = "GCP Project ID hosting the isolated spoke environment"
  type        = string
}

variable "hub_project_id" {
  description = "GCP Project ID of the Central Management Hub"
  type        = string
  default     = "majestic-energy-353306"
}

variable "region" {
  description = "GCP region for spoke compute, storage, and analytics"
  type        = string
  default     = "me-west1"
}

variable "environment" {
  description = "Deployment environment tier (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "admin_domain" {
  description = "Cloud Identity domain suffix for user and group emails"
  type        = string
  default     = "liatsabag.altostrat.com"
}

variable "shared_dataset_subscriptions" {
  description = "List of Hub shared dataset names this room is authorized to query"
  type        = list(string)
  default     = ["hub_shared_clinical", "hub_shared_reference"]
}

variable "researchers" {
  description = "List of researchers assigned to this research room"
  type = list(object({
    researcher_id = string
    first_name    = string
    last_name     = string
    primary_email = string
    role          = string
    access_state  = string # ACTIVE or DOWNGRADED
  }))
  default = []
}

variable "local_tables" {
  description = "List of local spoke tables to create with their schemas"
  type = list(object({
    table_id = string
    schema   = string
  }))
  default = []
}

variable "deletion_protection" {
  description = "Prevent accidental destruction of spoke resources"
  type        = bool
  default     = false
}

variable "enable_cloud_identity" {
  description = "Whether to provision Google Cloud Identity security groups and memberships directly"
  type        = bool
  default     = false
}

variable "enable_vpc_sc" {
  description = "Whether to attach spoke project to Access Context Manager VPC Service Perimeter"
  type        = bool
  default     = false
}

variable "access_policy_id" {
  description = "Access Context Manager Policy ID for VPC Service Controls"
  type        = string
  default     = null
}

variable "cmek_key_name" {
  description = "Optional Cloud KMS Key Name for CMEK storage and dataset encryption"
  type        = string
  default     = null
}

variable "hub_backend_sa_email" {
  description = "Service account email of the Hub Backend Gateway for quarantine bucket inspection"
  type        = string
  default     = null
}
