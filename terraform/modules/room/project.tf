/**
 * Project Services Enablement for Spoke Research Room
 * GCP Health Data Platform POC
 */

locals {
  spoke_services = [
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "notebooks.googleapis.com",
    "compute.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ]
}

# Enable required Google Cloud APIs for Spoke Research Room
resource "google_project_service" "spoke_services" {
  for_each                   = toset(locals.spoke_services)
  project                    = var.spoke_project_id
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}

# Cloud Logging project sink for security audit forwarding to Hub (optional/recommended)
resource "google_logging_project_sink" "spoke_audit_sink" {
  name        = "sink-${var.room_id}-audit-telemetry"
  project     = var.spoke_project_id
  description = "Routes spoke data access and notebook audit telemetry to BigQuery"

  # Routes logs to BigQuery dataset in spoke
  destination = "bigquery.googleapis.com/projects/${var.spoke_project_id}/datasets/${google_bigquery_dataset.spoke_local.dataset_id}"

  filter = "protoPayload.serviceName=(\"bigquery.googleapis.com\" OR \"storage.googleapis.com\" OR \"notebooks.googleapis.com\")"

  unique_writer_identity = true

  depends_on = [
    google_bigquery_dataset.spoke_local,
    google_project_service.spoke_services
  ]
}
