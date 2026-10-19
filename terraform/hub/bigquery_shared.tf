/**
 * BigQuery Shared Reference & Clinical Datasets and Tables for Central Management Hub
 * GCP Health Data Platform POC
 */

# --------------------------------------------------------------------------------------------------
# 1. Hub Shared Clinical Dataset & Tables
# --------------------------------------------------------------------------------------------------

resource "google_bigquery_dataset" "hub_shared_clinical" {
  dataset_id                 = "hub_shared_clinical"
  friendly_name              = "Hub Shared Clinical Vocabularies"
  description                = "Standardized ICD-10, OMOP and clinical reference catalogs shared with spoke rooms"
  location                   = var.region
  delete_contents_on_destroy = !var.deletion_protection
  labels                     = local.common_labels

  depends_on = [google_project_service.hub_services]
}

resource "google_bigquery_table" "icd10_catalogs" {
  dataset_id          = google_bigquery_dataset.hub_shared_clinical.dataset_id
  table_id            = "icd10_catalogs"
  description         = "ICD-10 clinical diagnostic code definitions"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "code", type = "STRING", mode = "REQUIRED" },
    { name = "description", type = "STRING", mode = "REQUIRED" },
    { name = "category", type = "STRING", mode = "REQUIRED" },
    { name = "chapter", type = "STRING", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "omop_vocabulary" {
  dataset_id          = google_bigquery_dataset.hub_shared_clinical.dataset_id
  table_id            = "omop_vocabulary"
  description         = "OMOP standardized concept vocabulary mappings"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "concept_id", type = "INT64", mode = "REQUIRED" },
    { name = "concept_name", type = "STRING", mode = "REQUIRED" },
    { name = "domain_id", type = "STRING", mode = "REQUIRED" },
    { name = "vocabulary_id", type = "STRING", mode = "REQUIRED" },
    { name = "concept_class_id", type = "STRING", mode = "REQUIRED" },
    { name = "standard_concept", type = "STRING", mode = "NULLABLE" }
  ])
}

# --------------------------------------------------------------------------------------------------
# 2. Hub Shared Reference Dataset & Tables
# --------------------------------------------------------------------------------------------------

resource "google_bigquery_dataset" "hub_shared_reference" {
  dataset_id                 = "hub_shared_reference"
  friendly_name              = "Hub Shared Reference Panels"
  description                = "Standard adult physiological lab ranges and clinical biomarker reference panels"
  location                   = var.region
  delete_contents_on_destroy = !var.deletion_protection
  labels                     = local.common_labels

  depends_on = [google_project_service.hub_services]
}

resource "google_bigquery_table" "reference_gene_panel" {
  dataset_id          = google_bigquery_dataset.hub_shared_reference.dataset_id
  table_id            = "reference_gene_panel"
  description         = "ClinVar and ACMG actionable biomarker panel reference"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "gene_symbol", type = "STRING", mode = "REQUIRED" },
    { name = "hgnc_id", type = "STRING", mode = "REQUIRED" },
    { name = "chromosome", type = "STRING", mode = "REQUIRED" },
    { name = "disease_association", type = "STRING", mode = "NULLABLE" },
    { name = "clinical_actionability", type = "STRING", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "standard_lab_ranges" {
  dataset_id          = google_bigquery_dataset.hub_shared_reference.dataset_id
  table_id            = "standard_lab_ranges"
  description         = "Standard clinical physiological laboratory reference intervals"
  deletion_protection = var.deletion_protection
  labels              = local.common_labels

  schema = jsonencode([
    { name = "test_name", type = "STRING", mode = "REQUIRED" },
    { name = "loinc_code", type = "STRING", mode = "REQUIRED" },
    { name = "unit", type = "STRING", mode = "REQUIRED" },
    { name = "normal_min", type = "FLOAT64", mode = "REQUIRED" },
    { name = "normal_max", type = "FLOAT64", mode = "REQUIRED" }
  ])
}
