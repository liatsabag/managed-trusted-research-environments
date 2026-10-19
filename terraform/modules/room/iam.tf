/**
 * Custom IAM Roles & Privilege Bindings for Spoke Research Room
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Custom IAM Roles: Active vs Soft-Policy Downgraded Reader
# --------------------------------------------------------------------------------------------------

resource "google_project_iam_custom_role" "active_researcher_role" {
  role_id     = "ResearchRoomActiveUser"
  title       = "Research Room Active Researcher"
  description = "Standard operational role: BigQuery querying, Inbound data read, Export quarantine staging, and Notebook compute"
  project     = var.spoke_project_id
  stage       = "GA"

  permissions = [
    "bigquery.jobs.create",
    "bigquery.tables.get",
    "bigquery.tables.getData",
    "bigquery.tables.list",
    "bigquery.datasets.get",
    "storage.buckets.get",
    "storage.objects.get",
    "storage.objects.list",
    "storage.objects.create",
    "notebooks.instances.get",
    "notebooks.instances.start",
    "notebooks.instances.stop",
    "notebooks.instances.use",
    "aiplatform.notebookRuntimes.get",
    "aiplatform.notebookRuntimes.assign"
  ]
}

resource "google_project_iam_custom_role" "downgraded_researcher_role" {
  role_id     = "ResearchRoomDowngradedReader"
  title       = "Research Room Downgraded Reader (Compliance Hold)"
  description = "Soft-policy compliance hold role: Revokes compute execution and writes, retaining read-only audit visibility"
  project     = var.spoke_project_id
  stage       = "GA"

  permissions = [
    "bigquery.datasets.get",
    "bigquery.tables.get",
    "bigquery.tables.getData",
    "bigquery.tables.list",
    "storage.buckets.get",
    "storage.objects.get",
    "storage.objects.list",
    "notebooks.instances.get"
  ]
}

# --------------------------------------------------------------------------------------------------
# 2. Project-Level IAM Bindings for Researchers
# --------------------------------------------------------------------------------------------------

# Active Researchers receive the Active User Role
resource "google_project_iam_member" "active_user_bindings" {
  for_each = { for r in local.active_researchers : r.primary_email => r }
  project  = var.spoke_project_id
  role     = google_project_iam_custom_role.active_researcher_role.id
  member   = "user:${each.key}"
}

# Downgraded Researchers receive only the Downgraded Reader Role
resource "google_project_iam_member" "downgraded_user_bindings" {
  for_each = { for r in local.downgraded_researchers : r.primary_email => r }
  project  = var.spoke_project_id
  role     = google_project_iam_custom_role.downgraded_researcher_role.id
  member   = "user:${each.key}"
}

# --------------------------------------------------------------------------------------------------
# 3. Hub Backend Gateway Service Account Bindings (for Gemini Scanning & Governance)
# --------------------------------------------------------------------------------------------------

resource "google_project_iam_member" "hub_backend_viewer" {
  count   = var.hub_backend_sa_email != null ? 1 : 0
  project = var.spoke_project_id
  role    = "roles/viewer"
  member  = "serviceAccount:${var.hub_backend_sa_email}"
}

resource "google_project_iam_member" "hub_backend_bq_user" {
  count   = var.hub_backend_sa_email != null ? 1 : 0
  project = var.spoke_project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${var.hub_backend_sa_email}"
}
