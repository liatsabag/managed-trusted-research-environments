/**
 * Main Provider & Core Configuration for Central Management Hub
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

  # Backend configuration can be configured for GCS remote state in production
  # backend "gcs" {
  #   bucket = "hub-mgmt-tfstate"
  #   prefix = "hub/state"
  # }
}

provider "google" {
  project = var.hub_project_id
  region  = var.region
}

provider "google-beta" {
  project = var.hub_project_id
  region  = var.region
}

locals {
  common_labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "hub-management-core"
    platform    = "gcp-health-tre"
  }

  hub_services = [
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "accesscontextmanager.googleapis.com",
    "cloudidentity.googleapis.com"
  ]
}

# Enable essential GCP API services on Hub Project
resource "google_project_service" "hub_services" {
  for_each                   = toset(locals.hub_services)
  project                    = var.hub_project_id
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}
