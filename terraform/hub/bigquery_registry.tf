/**
 * BigQuery Registry Dataset & Tables for Central Management Hub
 * GCP Health Data Platform POC
 */

resource "google_bigquery_dataset" "hub_registry" {
  dataset_id                 = "hub_registry"
  friendly_name              = "Hub Central Registry"
  description                = "Central master directories of partner institutes, approved researchers, research rooms, and tool inventories"
  location                   = var.region
  delete_contents_on_destroy = !var.deletion_protection
  labels                     = local.common_labels

  depends_on = [google_project_service.hub_services]
}

resource "google_bigquery_table" "reg_institutes" {
  dataset_id          = google_bigquery_dataset.hub_registry.dataset_id
  table_id            = "reg_institutes"
  description         = "Registered academic and clinical research partner institutions"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "institute_id", type = "STRING", mode = "REQUIRED", description = "Unique institute identifier" },
    { name = "name", type = "STRING", mode = "REQUIRED", description = "Full institute name" },
    { name = "contact_email", type = "STRING", mode = "REQUIRED", description = "Institutional contact email" },
    { name = "country", type = "STRING", mode = "REQUIRED", description = "Country code" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Onboarding timestamp" }
  ])
}

resource "google_bigquery_table" "reg_research_rooms" {
  dataset_id          = google_bigquery_dataset.hub_registry.dataset_id
  table_id            = "reg_research_rooms"
  description         = "Spoke Research Room tenant project registry and compliance status"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "room_name", type = "STRING", mode = "REQUIRED" },
    { name = "institute_id", type = "STRING", mode = "REQUIRED" },
    { name = "spoke_project_id", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "helsinki_expiry_date", type = "DATE", mode = "NULLABLE" },
    { name = "dua_expiry_date", type = "DATE", mode = "NULLABLE" },
    { name = "inbound_bucket", type = "STRING", mode = "REQUIRED" },
    { name = "export_bucket", type = "STRING", mode = "REQUIRED" },
    { name = "cloud_identity_group", type = "STRING", mode = "REQUIRED" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "reg_researchers" {
  dataset_id          = google_bigquery_dataset.hub_registry.dataset_id
  table_id            = "reg_researchers"
  description         = "Directory of verified researchers across all tenant rooms"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "researcher_id", type = "STRING", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "first_name", type = "STRING", mode = "REQUIRED" },
    { name = "last_name", type = "STRING", mode = "REQUIRED" },
    { name = "primary_email", type = "STRING", mode = "REQUIRED" },
    { name = "role", type = "STRING", mode = "REQUIRED" },
    { name = "access_state", type = "STRING", mode = "REQUIRED" },
    { name = "org_unit_path", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "reg_room_packages" {
  dataset_id          = google_bigquery_dataset.hub_registry.dataset_id
  table_id            = "reg_room_packages"
  description         = "Governed software packages and tools authorized within research rooms"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "package_id", type = "STRING", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "package_name", type = "STRING", mode = "REQUIRED" },
    { name = "version", type = "STRING", mode = "REQUIRED" },
    { name = "ecosystem", type = "STRING", mode = "REQUIRED" },
    { name = "license", type = "STRING", mode = "REQUIRED" },
    { name = "security_status", type = "STRING", mode = "REQUIRED" }
  ])
}
