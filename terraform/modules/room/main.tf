/**
 * Main Configuration & Locals for Spoke Research Room Module
 * GCP Health Data Platform POC
 */

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
  }
}

locals {
  room_labels = {
    environment   = var.environment
    managed_by    = "terraform"
    room_id       = var.room_id
    institute_id  = var.institute_id
    platform      = "gcp-health-tre"
  }

  inbound_bucket_name = "${var.spoke_project_id}-inbound"
  export_bucket_name  = "${var.spoke_project_id}-export"
  group_email         = "gcp-${var.room_id}-researchers@${var.admin_domain}"

  # Filter researchers by active vs downgraded access state
  active_researchers = [
    for r in var.researchers : r if r.access_state == "ACTIVE"
  ]

  downgraded_researchers = [
    for r in var.researchers : r if r.access_state == "DOWNGRADED"
  ]
}
