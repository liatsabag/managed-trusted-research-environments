/**
 * Outputs for Spoke Research Room Module
 * GCP Health Data Platform POC
 */

output "room_id" {
  description = "Unique Research Room identifier"
  value       = var.room_id
}

output "spoke_project_id" {
  description = "GCP Project ID hosting the spoke environment"
  value       = var.spoke_project_id
}

output "inbound_bucket_name" {
  description = "Name of the inbound sanitized clinical data bucket"
  value       = google_storage_bucket.inbound_bucket.name
}

output "inbound_bucket_url" {
  description = "GCS URI for the inbound sanitized clinical data bucket"
  value       = "gs://${google_storage_bucket.inbound_bucket.name}"
}

output "export_bucket_name" {
  description = "Name of the outbound quarantine staging bucket"
  value       = google_storage_bucket.export_bucket.name
}

output "export_bucket_url" {
  description = "GCS URI for the outbound quarantine staging bucket"
  value       = "gs://${google_storage_bucket.export_bucket.name}"
}

output "local_dataset_id" {
  description = "Dataset ID of the spoke local BigQuery workspace"
  value       = google_bigquery_dataset.spoke_local.dataset_id
}

output "identity_group_email" {
  description = "Cloud Identity security group email for room researchers"
  value       = local.group_email
}

output "notebook_service_account_email" {
  description = "Governed service account email bound to notebook runtimes"
  value       = google_service_account.notebook_sa.email
}

output "workbench_instance_id" {
  description = "ID of the provisioned Vertex AI Workbench instance"
  value       = google_workbench_instance.research_workbench.id
}
