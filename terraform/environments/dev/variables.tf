/**
 * Variables for Dev Environment Root Configuration
 * GCP Health Data Platform POC
 */

variable "environment" {
  description = "Target deployment environment"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "Default Google Cloud region"
  type        = string
  default     = "me-west1"
}

variable "hub_project_id" {
  description = "GCP Project ID hosting the Central Management Hub"
  type        = string
  default     = "gcp-rr-hub-core"
}

variable "billing_project_id" {
  description = "GCP Project ID hosting the master Cloud Billing BigQuery export"
  type        = string
  default     = "gcp-rr-hub-core"
}

variable "billing_dataset_id" {
  description = "Dataset ID containing the Cloud Billing export"
  type        = string
  default     = "billing"
}

variable "billing_export_table" {
  description = "Table name or pattern for Cloud Billing export"
  type        = string
  default     = "gcp_billing_export_v1"
}

variable "admin_domain" {
  description = "Cloud Identity / Google Workspace organization domain"
  type        = string
  default     = "liatsabag.altostrat.com"
}

variable "deletion_protection" {
  description = "Enable deletion protection on datasets and tables"
  type        = bool
  default     = false
}

variable "enable_vpc_sc" {
  description = "Whether to deploy Access Context Manager VPC Service Controls perimeters"
  type        = bool
  default     = false
}

variable "access_policy_id" {
  description = "Access Context Manager Policy numeric ID (required if enable_vpc_sc is true)"
  type        = string
  default     = null
}

variable "ops_admin_members" {
  description = "List of Central Operations Admin identity members (user: email or group: email)"
  type        = list(string)
  default     = []
}

variable "tech_admin_members" {
  description = "List of Technical Cloud Admin identity members (user: email or group: email)"
  type        = list(string)
  default     = []
}

variable "dpo_members" {
  description = "List of Data Privacy Officer identity members (user: email or group: email)"
  type        = list(string)
  default     = []
}
