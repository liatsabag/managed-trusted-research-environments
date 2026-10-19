-- scripts/sql/schema_hub_shared.sql
-- Hub Shared Datasets: Clinical Catalogs and Genomic Reference Panels

-- 1. Shared Clinical Terminology Dataset
CREATE SCHEMA IF NOT EXISTS `hub_shared_clinical`
OPTIONS(
  location = 'me-west1',
  description = 'Cross-spoke sanitized clinical terminology and reference catalogs'
);

-- ICD-10 Diagnostic Coding Catalog
CREATE TABLE IF NOT EXISTS `hub_shared_clinical.icd10_catalogs` (
    icd10_code STRING NOT NULL,
    code_description STRING NOT NULL,
    chapter STRING NOT NULL,
    block STRING NOT NULL,
    is_valid_clinical_concept BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- OMOP CDM Concept Vocabulary
CREATE TABLE IF NOT EXISTS `hub_shared_clinical.omop_vocabulary` (
    concept_id INT64 NOT NULL,
    concept_name STRING NOT NULL,
    domain_id STRING NOT NULL,
    vocabulary_id STRING NOT NULL,
    concept_class_id STRING NOT NULL,
    standard_concept STRING,
    concept_code STRING NOT NULL,
    valid_start_date DATE NOT NULL,
    valid_end_date DATE NOT NULL
);

-- 2. Shared Reference Dataset
CREATE SCHEMA IF NOT EXISTS `hub_shared_reference`
OPTIONS(
  location = 'me-west1',
  description = 'Genomic panels and standardized physiological reference ranges'
);

-- Reference Gene Biomarker Panel
CREATE TABLE IF NOT EXISTS `hub_shared_reference.reference_gene_panel` (
    gene_symbol STRING NOT NULL,
    gene_id STRING NOT NULL,
    chromosome STRING NOT NULL,
    locus_start INT64 NOT NULL,
    locus_end INT64 NOT NULL,
    clinical_significance STRING NOT NULL,
    disease_association STRING NOT NULL,
    inheritance_mode STRING,
    acmg_tier STRING
);

-- Standard Laboratory Reference Ranges
CREATE TABLE IF NOT EXISTS `hub_shared_reference.standard_lab_ranges` (
    test_code STRING NOT NULL,
    test_name STRING NOT NULL,
    specimen_type STRING NOT NULL,
    low_normal_val FLOAT64 NOT NULL,
    high_normal_val FLOAT64 NOT NULL,
    unit_of_measure STRING NOT NULL,
    age_group STRING DEFAULT 'ADULT',
    sex STRING DEFAULT 'ALL'
);
