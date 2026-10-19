/**
 * Outputs for Central Management Hub Module
 * GCP Health Data Platform POC
 */

output "hub_project_id" {
  description = "The Project ID of the Central Management Hub"
  value       = var.hub_project_id
}

output "hub_registry_dataset_id" {
  description = "Dataset ID of the Hub Central Registry"
  value       = google_bigquery_dataset.hub_registry.dataset_id
}

output "hub_telemetry_dataset_id" {
  description = "Dataset ID of the Hub Operational Telemetry"
  value       = google_bigquery_dataset.hub_telemetry.dataset_id
}

output "hub_shared_clinical_dataset_id" {
  description = "Dataset ID of the Hub Shared Clinical Vocabularies"
  value       = google_bigquery_dataset.hub_shared_clinical.dataset_id
}

output "hub_shared_reference_dataset_id" {
  description = "Dataset ID of the Hub Shared Reference Panels"
  value       = google_bigquery_dataset.hub_shared_reference.dataset_id
}

output "view_billing_export_id" {
  description = "Resource ID of the authorized billing export view"
  value       = google_bigquery_table.view_billing_export.id
}

output "hub_service_perimeter_name" {
  description = "Name of the Hub VPC Service Controls perimeter (if enabled)"
  value       = var.enable_vpc_sc && var.access_policy_id != null ? google_access_context_manager_service_perimeter.hub_perimeter[0].name : null
}

output "hub_backend_service_account_email" {
  description = "Email of the Hub Backend Gateway Service Account"
  value       = google_service_account.hub_backend.email
}

output "custom_role_ops_admin" {
  description = "Custom Role ID for Central Operations Admin"
  value       = google_project_iam_custom_role.central_ops_admin.id
}

output "custom_role_tech_admin" {
  description = "Custom Role ID for Technical Cloud Admin"
  value       = google_project_iam_custom_role.tech_cloud_admin.id
}

output "custom_role_dpo" {
  description = "Custom Role ID for Data Privacy Officer"
  value       = google_project_iam_custom_role.data_privacy_officer.id
}
