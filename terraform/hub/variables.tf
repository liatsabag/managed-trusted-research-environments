/**
 * Variables for the Central Management Hub Infrastructure
 * GCP Health Data Platform POC
 */

variable "hub_project_id" {
  description = "The GCP Project ID hosting the Central Management Hub"
  type        = string
  default     = "majestic-energy-353306"
}

variable "region" {
  description = "Default Google Cloud region for Hub resources"
  type        = string
  default     = "me-west1"
}

variable "billing_project_id" {
  description = "External GCP project hosting the master Cloud Billing BigQuery export"
  type        = string
  default     = "majestic-energy-353306"
}

variable "billing_dataset_id" {
  description = "Dataset ID inside the billing project containing export tables"
  type        = string
  default     = "billing"
}

variable "billing_export_table" {
  description = "Table name or pattern for standard/detailed GCP billing export"
  type        = string
  default     = "gcp_billing_export_v1"
}

variable "admin_domain" {
  description = "Primary Cloud Identity / Google Workspace domain for central administrators"
  type        = string
  default     = "healthhub.org"
}

variable "deletion_protection" {
  description = "Whether to prevent accidental deletion of BigQuery datasets and tables"
  type        = bool
  default     = false
}

variable "enable_vpc_sc" {
  description = "Flag to enable Access Context Manager VPC Service Controls perimeter"
  type        = bool
  default     = false
}

variable "access_policy_id" {
  description = "Access Context Manager Policy numeric ID (required if enable_vpc_sc is true)"
  type        = string
  default     = null
}

variable "ops_admin_members" {
  description = "IAM identity principals assigned to Central Operations Admin role"
  type        = list(string)
  default     = []
}

variable "tech_admin_members" {
  description = "IAM identity principals assigned to Technical Cloud Admin role"
  type        = list(string)
  default     = []
}

variable "dpo_members" {
  description = "IAM identity principals assigned to Data Privacy Officer role"
  type        = list(string)
  default     = []
}

variable "environment" {
  description = "Environment identifier (dev, staging, prod)"
  type        = string
  default     = "dev"
}
