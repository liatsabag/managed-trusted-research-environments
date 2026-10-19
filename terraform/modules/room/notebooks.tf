/**
 * Governed Notebook Runtimes & Workbench Environment for Spoke Research Room
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Governed Service Account for Colab Enterprise / Workbench Notebooks
# --------------------------------------------------------------------------------------------------

resource "google_service_account" "notebook_sa" {
  account_id   = "sa-rr-${local.room_short_name}-compute"
  project      = var.spoke_project_id
  display_name = "${var.room_name} Governed Notebook Service Account"
  description  = "Restricted service account bound to researcher interactive notebook runtime sessions"
}

# Grant Notebook Service Account access to query BigQuery and read Inbound storage
resource "google_project_iam_member" "notebook_sa_bq_job_user" {
  project = var.spoke_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.notebook_sa.email}"
}

resource "google_project_iam_member" "notebook_sa_bq_data_viewer" {
  project = var.spoke_project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.notebook_sa.email}"
}

# --------------------------------------------------------------------------------------------------
# 2. Governed Vertex AI Workbench Runtime Instance Template
# --------------------------------------------------------------------------------------------------

resource "google_workbench_instance" "research_workbench" {
  name     = "wb-${local.room_short_name}-governed"
  project  = var.spoke_project_id
  location = "${var.region}-a"

  gce_setup {
    machine_type = "e2-standard-4"

    service_accounts {
      email = google_service_account.notebook_sa.email
    }

    disable_public_ip = true

    shielded_instance_config {
      enable_secure_boot          = true
      enable_vtpm                 = true
      enable_integrity_monitoring = true
    }

    metadata = {
      terraform              = "true"
      room_id                = var.room_id
      institute_id           = var.institute_id
      inbound_bucket         = google_storage_bucket.inbound_bucket.name
      export_quarantine_bucket = google_storage_bucket.export_bucket.name
      report-system-health   = "true"
    }
  }

  labels = local.room_labels

  depends_on = [
    google_project_service.spoke_services,
    google_storage_bucket.inbound_bucket,
    google_storage_bucket.export_bucket
  ]
}
