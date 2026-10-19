/**
 * Custom IAM Roles and Bindings for Central Management Hub
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Custom IAM Roles
# --------------------------------------------------------------------------------------------------

resource "google_project_iam_custom_role" "central_ops_admin" {
  role_id     = "CentralOperationsAdmin"
  title       = "Central Operations Administrator"
  description = "Governance oversight, researcher directories, compliance verification, and FinOps visibility"
  project     = var.hub_project_id
  stage       = "GA"

  permissions = [
    "bigquery.datasets.get",
    "bigquery.jobs.create",
    "bigquery.tables.get",
    "bigquery.tables.getData",
    "bigquery.tables.list",
    "resourcemanager.projects.get",
    "logging.logEntries.list",
    "monitoring.timeSeries.list"
  ]
}

resource "google_project_iam_custom_role" "tech_cloud_admin" {
  role_id     = "TechnicalCloudAdmin"
  title       = "Technical Cloud Administrator"
  description = "Infrastructure lifecycle management, dual-bucket storage, and runtime configurations"
  project     = var.hub_project_id
  stage       = "GA"

  permissions = [
    "bigquery.datasets.create",
    "bigquery.datasets.get",
    "bigquery.datasets.update",
    "bigquery.tables.create",
    "bigquery.tables.get",
    "bigquery.tables.update",
    "storage.buckets.get",
    "storage.buckets.list",
    "storage.objects.get",
    "storage.objects.list",
    "resourcemanager.projects.get",
    "logging.views.access"
  ]
}

resource "google_project_iam_custom_role" "data_privacy_officer" {
  role_id     = "DataPrivacyOfficer"
  title       = "Data Privacy Officer (DPO)"
  description = "Air-Lock review queue inspection, Gemini risk card review, and egress approval"
  project     = var.hub_project_id
  stage       = "GA"

  permissions = [
    "bigquery.tables.get",
    "bigquery.tables.getData",
    "storage.objects.get",
    "storage.objects.list",
    "aiplatform.endpoints.predict"
  ]
}

# --------------------------------------------------------------------------------------------------
# 2. Hub Backend Service Account
# --------------------------------------------------------------------------------------------------

resource "google_service_account" "hub_backend" {
  account_id   = "sa-hub-backend-api"
  display_name = "Hub Central Gateway Backend Service Account"
  description  = "Identity utilized by the central FastAPI backend and automated fleet governance services"
  project      = var.hub_project_id
}

resource "google_project_iam_member" "hub_backend_bq_admin" {
  project = var.hub_project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.hub_backend.email}"
}

resource "google_project_iam_member" "hub_backend_ai_user" {
  project = var.hub_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.hub_backend.email}"
}

resource "google_project_iam_member" "hub_backend_log_writer" {
  project = var.hub_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.hub_backend.email}"
}

# --------------------------------------------------------------------------------------------------
# 3. Role Assignments to Administrator Identities
# --------------------------------------------------------------------------------------------------

resource "google_project_iam_member" "ops_admin_bindings" {
  for_each = toset(var.ops_admin_members)
  project  = var.hub_project_id
  role     = google_project_iam_custom_role.central_ops_admin.id
  member   = each.key
}

resource "google_project_iam_member" "tech_admin_bindings" {
  for_each = toset(var.tech_admin_members)
  project  = var.hub_project_id
  role     = google_project_iam_custom_role.tech_cloud_admin.id
  member   = each.key
}

resource "google_project_iam_member" "dpo_bindings" {
  for_each = toset(var.dpo_members)
  project  = var.hub_project_id
  role     = google_project_iam_custom_role.data_privacy_officer.id
  member   = each.key
}
