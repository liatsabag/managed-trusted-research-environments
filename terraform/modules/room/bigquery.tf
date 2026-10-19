/**
 * BigQuery Dataset & Cross-Project Subscriptions for Spoke Research Room
 * GCP Health Data Platform POC
 */

locals {
  # Automatically parse "oncology" from "rr-oncology-01"
  room_short_name  = length(split("-", var.room_id)) >= 2 ? split("-", var.room_id)[1] : var.room_id
  local_dataset_id = "spoke_local_${local.room_short_name}"
}

# --------------------------------------------------------------------------------------------------
# 1. Local Spoke Work Dataset
# --------------------------------------------------------------------------------------------------

resource "google_bigquery_dataset" "spoke_local" {
  dataset_id                  = local.local_dataset_id
  project                     = var.spoke_project_id
  friendly_name               = "${var.room_name} Local Data"
  description                 = "Isolated analytics work dataset for ${var.room_name} (${var.room_id})"
  location                    = var.region
  delete_contents_on_destroy  = !var.deletion_protection
  labels                      = local.room_labels

  dynamic "default_encryption_configuration" {
    for_each = var.cmek_key_name != null ? [1] : []
    content {
      kms_key_name = var.cmek_key_name
    }
  }

  depends_on = [google_project_service.spoke_services]
}

# Grant Researchers Data Viewer rights on the Local Dataset
resource "google_bigquery_dataset_iam_member" "researchers_local_viewer" {
  dataset_id = google_bigquery_dataset.spoke_local.dataset_id
  project    = var.spoke_project_id
  role       = "roles/bigquery.dataViewer"
  member     = var.enable_cloud_identity ? "group:${local.group_email}" : "projectViewer:${var.spoke_project_id}"
}

# Grant Active Researchers Data Editor rights to create intermediate analysis tables
resource "google_bigquery_dataset_iam_member" "active_researchers_editor" {
  for_each   = { for r in local.active_researchers : r.primary_email => r }
  dataset_id = google_bigquery_dataset.spoke_local.dataset_id
  project    = var.spoke_project_id
  role       = "roles/bigquery.dataEditor"
  member     = "user:${each.key}"
}

# --------------------------------------------------------------------------------------------------
# 2. Cross-Project Authorized Views for Subscribed Hub Shared Datasets
# --------------------------------------------------------------------------------------------------

# Authorized federated view for Hub Shared Clinical Vocabulary (if subscribed)
resource "google_bigquery_table" "view_shared_clinical" {
  count               = contains(var.shared_dataset_subscriptions, "hub_shared_clinical") ? 1 : 0
  project             = var.spoke_project_id
  dataset_id          = google_bigquery_dataset.spoke_local.dataset_id
  table_id            = "view_hub_shared_clinical"
  description         = "Cross-project authorized view into Hub Shared Clinical terminology"
  deletion_protection = var.deletion_protection
  labels              = local.room_labels

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT *
      FROM `${var.hub_project_id}.hub_shared_clinical.icd10_catalogs`
    SQL
  }
}

# Authorized federated view for Hub Shared Reference Panels (if subscribed)
resource "google_bigquery_table" "view_shared_reference" {
  count               = contains(var.shared_dataset_subscriptions, "hub_shared_reference") ? 1 : 0
  project             = var.spoke_project_id
  dataset_id          = google_bigquery_dataset.spoke_local.dataset_id
  table_id            = "view_hub_shared_reference"
  description         = "Cross-project authorized view into Hub Shared Reference Gene Panels"
  deletion_protection = var.deletion_protection
  labels              = local.room_labels

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT *
      FROM `${var.hub_project_id}.hub_shared_reference.reference_gene_panel`
    SQL
  }
}
