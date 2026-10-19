/**
 * Dual-Bucket Storage Architecture for Spoke Research Room
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Inbound Verified Read-Only GCS Bucket
# --------------------------------------------------------------------------------------------------

resource "google_storage_bucket" "inbound_bucket" {
  name                        = local.inbound_bucket_name
  project                     = var.spoke_project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection
  labels                      = local.room_labels

  versioning {
    enabled = true
  }

  dynamic "encryption" {
    for_each = var.cmek_key_name != null ? [1] : []
    content {
      default_kms_key_name = var.cmek_key_name
    }
  }

  depends_on = [google_project_service.spoke_services]
}

# Researchers have strictly Read-Only access to Inbound Sanitized Data
resource "google_storage_bucket_iam_member" "inbound_researchers_read" {
  bucket = google_storage_bucket.inbound_bucket.name
  role   = "roles/storage.objectViewer"
  member = var.enable_cloud_identity ? "group:${local.group_email}" : "projectViewer:${var.spoke_project_id}"
}

# --------------------------------------------------------------------------------------------------
# 2. Outbound Export Quarantine GCS Bucket (Air-Lock Staging)
# --------------------------------------------------------------------------------------------------

resource "google_storage_bucket" "export_bucket" {
  name                        = local.export_bucket_name
  project                     = var.spoke_project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection
  labels                      = local.room_labels

  versioning {
    enabled = true
  }

  # Retain quarantine audit artifacts for 90 days before archiving
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90
    }
  }

  dynamic "encryption" {
    for_each = var.cmek_key_name != null ? [1] : []
    content {
      default_kms_key_name = var.cmek_key_name
    }
  }

  depends_on = [google_project_service.spoke_services]
}

# Active Researchers can upload candidate analysis results to the Export Quarantine Bucket
resource "google_storage_bucket_iam_member" "export_researchers_create" {
  for_each = { for r in local.active_researchers : r.primary_email => r }
  bucket   = google_storage_bucket.export_bucket.name
  role     = "roles/storage.objectCreator"
  member   = "user:${each.key}"
}

resource "google_storage_bucket_iam_member" "export_researchers_view" {
  for_each = { for r in local.active_researchers : r.primary_email => r }
  bucket   = google_storage_bucket.export_bucket.name
  role     = "roles/storage.objectViewer"
  member   = "user:${each.key}"
}

# Hub Backend Service Account access to read quarantine objects for Gemini Risk Card assessment
resource "google_storage_bucket_iam_member" "hub_backend_quarantine_reader" {
  count  = var.hub_backend_sa_email != null ? 1 : 0
  bucket = google_storage_bucket.export_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.hub_backend_sa_email}"
}
