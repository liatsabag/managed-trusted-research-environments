/**
 * BigQuery Telemetry Dataset, Tables & Authorized View for Central Management Hub
 * GCP Health Data Platform POC
 */

resource "google_bigquery_dataset" "hub_telemetry" {
  dataset_id                 = "hub_telemetry"
  friendly_name              = "Hub Operational Telemetry"
  description                = "Regulatory checklist status, Air-Lock egress logs, FinOps views, and audit marts"
  location                   = var.region
  delete_contents_on_destroy = !var.deletion_protection
  labels                     = local.common_labels

  depends_on = [google_project_service.hub_services]
}

resource "google_bigquery_table" "ops_regulatory_checklist" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_regulatory_checklist"
  description         = "5-item regulatory gating audit checklist per research room"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "checklist_id", type = "STRING", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "item_key", type = "STRING", mode = "REQUIRED" },
    { name = "title", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "approved_date", type = "DATE", mode = "NULLABLE" },
    { name = "expiry_date", type = "DATE", mode = "NULLABLE" },
    { name = "document_uri", type = "STRING", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "ops_airlock_requests" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_airlock_requests"
  description         = "Air-Lock egress requests and automated Gemini risk card evaluations"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "request_id", type = "STRING", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "researcher_email", type = "STRING", mode = "REQUIRED" },
    { name = "source_file_uri", type = "STRING", mode = "REQUIRED" },
    { name = "file_name", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "risk_score", type = "INT64", mode = "NULLABLE" },
    { name = "risk_level", type = "STRING", mode = "NULLABLE" },
    { name = "gemini_rationale", type = "STRING", mode = "NULLABLE" },
    { name = "flagged_columns", type = "STRING", mode = "NULLABLE" },
    { name = "dpo_reviewer", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "sla_deadline", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "ops_audit_events_curated" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_audit_events_curated"
  description         = "Curated operational audit events dynamically resolved across active research rooms"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["room_id", "category", "principal_email"]

  schema = jsonencode([
    { name = "log_id", type = "STRING", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "project_id", type = "STRING", mode = "REQUIRED" },
    { name = "principal_email", type = "STRING", mode = "REQUIRED" },
    { name = "category", type = "STRING", mode = "REQUIRED" },
    { name = "service_name", type = "STRING", mode = "REQUIRED" },
    { name = "action_name", type = "STRING", mode = "REQUIRED" },
    { name = "resource_name", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "severity", type = "STRING", mode = "REQUIRED" },
    { name = "description", type = "STRING", mode = "REQUIRED" },
    { name = "metadata_json", type = "STRING", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "ops_notebook_sessions" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_notebook_sessions"
  description         = "Persisted daily Colab Enterprise and BigQuery Studio notebook runtime sessions per researcher"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "session_date"
  }

  clustering = ["room_id", "user_email", "runtime_template_id"]

  schema = jsonencode([
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "user_email", type = "STRING", mode = "REQUIRED" },
    { name = "session_date", type = "DATE", mode = "REQUIRED" },
    { name = "notebook_name", type = "STRING", mode = "NULLABLE" },
    { name = "runtime_id", type = "STRING", mode = "NULLABLE" },
    { name = "machine_type", type = "STRING", mode = "NULLABLE" },
    { name = "runtime_template_id", type = "STRING", mode = "NULLABLE" },
    { name = "total_events", type = "INT64", mode = "NULLABLE" },
    { name = "session_starts", type = "INT64", mode = "NULLABLE" },
    { name = "session_stops", type = "INT64", mode = "NULLABLE" },
    { name = "total_sessions", type = "INT64", mode = "NULLABLE" },
    { name = "total_active_hours", type = "NUMERIC", mode = "NULLABLE" },
    { name = "first_session_start", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "last_session_end", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "ops_ai_usage_metrics" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_ai_usage_metrics"
  description         = "Persisted daily AI and Gemini inference invocation counts per researcher"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "usage_date"
  }

  clustering = ["room_id", "user_email"]

  schema = jsonencode([
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "project_id", type = "STRING", mode = "REQUIRED" },
    { name = "user_email", type = "STRING", mode = "REQUIRED" },
    { name = "usage_date", type = "DATE", mode = "REQUIRED" },
    { name = "service_name", type = "STRING", mode = "REQUIRED" },
    { name = "total_inference_calls", type = "INT64", mode = "NULLABLE" },
    { name = "successful_calls", type = "INT64", mode = "NULLABLE" },
    { name = "failed_calls", type = "INT64", mode = "NULLABLE" },
    { name = "first_invoked_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "last_invoked_at", type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "ops_daily_compute_metrics" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_daily_compute_metrics"
  description         = "Unified daily compute, AI inference, and storage usage metrics per researcher"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "usage_date"
  }

  clustering = ["room_id", "user_email"]

  schema = jsonencode([
    { name = "usage_date", type = "DATE", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "user_email", type = "STRING", mode = "REQUIRED" },
    { name = "institute_id", type = "STRING", mode = "NULLABLE" },
    { name = "query_count", type = "INT64", mode = "NULLABLE" },
    { name = "total_bytes_billed", type = "INT64", mode = "NULLABLE" },
    { name = "total_slot_hours", type = "NUMERIC", mode = "NULLABLE" },
    { name = "notebook_runtime_hours", type = "NUMERIC", mode = "NULLABLE" },
    { name = "ai_inference_count", type = "INT64", mode = "NULLABLE" },
    { name = "ai_token_count", type = "INT64", mode = "NULLABLE" },
    { name = "storage_bytes", type = "INT64", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "ops_monthly_usage_rollup" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "ops_monthly_usage_rollup"
  description         = "Monthly rollup of compute, active researchers, and query volume per room"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  time_partitioning {
    type  = "DAY"
    field = "usage_month"
  }

  clustering = ["room_id", "institute_id"]

  schema = jsonencode([
    { name = "usage_month", type = "DATE", mode = "REQUIRED" },
    { name = "room_id", type = "STRING", mode = "REQUIRED" },
    { name = "institute_id", type = "STRING", mode = "REQUIRED" },
    { name = "avg_active_researchers", type = "NUMERIC", mode = "NULLABLE" },
    { name = "total_notebook_hours", type = "NUMERIC", mode = "NULLABLE" },
    { name = "total_query_volume_tb", type = "NUMERIC", mode = "NULLABLE" },
    { name = "total_slot_hours", type = "NUMERIC", mode = "NULLABLE" }
  ])
}

# Authorized Billing Export View connecting to external billing export
resource "google_bigquery_table" "view_billing_export" {
  dataset_id          = google_bigquery_dataset.hub_telemetry.dataset_id
  table_id            = "view_billing_export"
  description         = "Authorized FinOps view filtered on research room spoke projects"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        billing_account_id,
        service.id AS service_id,
        service.description AS service_description,
        sku.id AS sku_id,
        sku.description AS sku_description,
        usage_start_time,
        usage_end_time,
        project.id AS project_id,
        project.name AS project_name,
        labels,
        cost,
        currency,
        usage.amount AS usage_amount,
        usage.unit AS usage_unit,
        invoice.month AS invoice_month
      FROM `${var.billing_project_id}.${var.billing_dataset_id}.${var.billing_export_table}`
      WHERE project.id LIKE 'gcp-rr-%' OR project.id LIKE 'tre-room-%' OR project.id = '${var.hub_project_id}'
    SQL
  }
}
