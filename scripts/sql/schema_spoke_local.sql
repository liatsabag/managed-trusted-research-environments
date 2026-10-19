-- scripts/sql/schema_spoke_local.sql
-- Spoke Local Datasets & Tables DDL (Oncology, Genomics, Cardio, Neurology)

-- ============================================================================
-- 1. SPOKE LOCAL ONCOLOGY (spoke_local_oncology)
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS `spoke_local_oncology`
OPTIONS(location = 'me-west1', description = 'Immuno-oncology patient cohort and clinical response');

CREATE TABLE IF NOT EXISTS `spoke_local_oncology.patient_cohort` (
    patient_id STRING NOT NULL,
    enrollment_date DATE NOT NULL,
    age INT64 NOT NULL,
    biological_sex STRING NOT NULL,
    primary_diagnosis STRING NOT NULL,
    stage STRING NOT NULL,
    ecog_ps INT64,
    smoker_status STRING,
    vital_status STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_oncology.tumor_markers` (
    marker_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    test_date DATE NOT NULL,
    marker_name STRING NOT NULL,
    quantitative_val FLOAT64 NOT NULL,
    unit STRING NOT NULL,
    reference_range STRING,
    flag_abnormal BOOLEAN
);

CREATE TABLE IF NOT EXISTS `spoke_local_oncology.treatment_outcomes` (
    outcome_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    line_of_therapy INT64 NOT NULL,
    regimen_name STRING NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    best_overall_response STRING NOT NULL,
    progression_free_survival_days INT64,
    adverse_event_grade INT64
);

CREATE TABLE IF NOT EXISTS `spoke_local_oncology.immunotherapy_response` (
    response_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    checkpoint_inhibitor STRING NOT NULL,
    pd_l1_tps_percent FLOAT64 NOT NULL,
    tmb_score FLOAT64 NOT NULL,
    response_category STRING NOT NULL,
    recist_1_1 STRING NOT NULL,
    immune_adverse_event BOOLEAN
);

-- ============================================================================
-- 2. SPOKE LOCAL GENOMICS (spoke_local_genomics)
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS `spoke_local_genomics`
OPTIONS(location = 'me-west1', description = 'Rare disease whole-genome sequencing calls and manifests');

CREATE TABLE IF NOT EXISTS `spoke_local_genomics.variant_calls` (
    variant_id STRING NOT NULL,
    sample_id STRING NOT NULL,
    chromosome STRING NOT NULL,
    position INT64 NOT NULL,
    ref_allele STRING NOT NULL,
    alt_allele STRING NOT NULL,
    genotype STRING NOT NULL,
    filter_status STRING NOT NULL,
    depth INT64 NOT NULL,
    allele_frequency FLOAT64 NOT NULL,
    clinvar_id STRING,
    pathogenicity STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_genomics.sample_manifests` (
    sample_id STRING NOT NULL,
    subject_id STRING NOT NULL,
    tissue_type STRING NOT NULL,
    sequencing_type STRING NOT NULL,
    platform STRING NOT NULL,
    mean_coverage FLOAT64 NOT NULL,
    percent_q30 FLOAT64 NOT NULL,
    library_prep_date DATE NOT NULL,
    batch_id STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_genomics.phenotype_mapping` (
    phenotype_id STRING NOT NULL,
    subject_id STRING NOT NULL,
    hpo_id STRING NOT NULL,
    hpo_term STRING NOT NULL,
    onset_age_years FLOAT64,
    modifier STRING,
    confirmed_flag BOOLEAN DEFAULT TRUE
);

-- ============================================================================
-- 3. SPOKE LOCAL CARDIO (spoke_local_cardio)
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS `spoke_local_cardio`
OPTIONS(location = 'me-west1', description = 'Cardiovascular telemetry, lipid biomarkers, and cardiac events');

CREATE TABLE IF NOT EXISTS `spoke_local_cardio.ecg_telemetry_metrics` (
    recording_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    heart_rate_bpm FLOAT64 NOT NULL,
    pr_interval_ms FLOAT64 NOT NULL,
    qrs_duration_ms FLOAT64 NOT NULL,
    qtc_interval_ms FLOAT64 NOT NULL,
    rhythm_interpretation STRING NOT NULL,
    st_segment_elevation BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_cardio.lipid_profiles` (
    lipid_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    sample_date DATE NOT NULL,
    total_cholesterol_mg_dl FLOAT64 NOT NULL,
    hdl_mg_dl FLOAT64 NOT NULL,
    ldl_mg_dl FLOAT64 NOT NULL,
    triglycerides_mg_dl FLOAT64 NOT NULL,
    hs_crp_mg_l FLOAT64 NOT NULL,
    statin_therapy BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_cardio.patient_registry` (
    patient_id STRING NOT NULL,
    enrollment_date DATE NOT NULL,
    age_at_intake INT64 NOT NULL,
    sex STRING NOT NULL,
    baseline_sbp INT64 NOT NULL,
    baseline_dbp INT64 NOT NULL,
    bmi FLOAT64 NOT NULL,
    hypertension_history BOOLEAN NOT NULL,
    diabetes_history BOOLEAN NOT NULL,
    smoker BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_cardio.cardiac_events` (
    event_id STRING NOT NULL,
    patient_id STRING NOT NULL,
    event_date DATE NOT NULL,
    event_type STRING NOT NULL,
    adjudicated_flag BOOLEAN NOT NULL,
    nyha_class STRING,
    ejection_fraction_percent FLOAT64,
    intervention STRING
);

-- ============================================================================
-- 4. SPOKE LOCAL NEUROLOGY (spoke_local_neurology)
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS `spoke_local_neurology`
OPTIONS(location = 'me-west1', description = 'Neurodegenerative clinical trial, cognitive assessments, and MRI features');

CREATE TABLE IF NOT EXISTS `spoke_local_neurology.cognitive_assessments` (
    assessment_id STRING NOT NULL,
    participant_id STRING NOT NULL,
    assessment_date DATE NOT NULL,
    mmse_score INT64 NOT NULL,
    adas_cog_score FLOAT64 NOT NULL,
    cdr_sum_of_boxes FLOAT64 NOT NULL,
    mo_ca_score INT64 NOT NULL,
    clinician_notes_summary STRING
);

CREATE TABLE IF NOT EXISTS `spoke_local_neurology.mri_volumetric_features` (
    scan_id STRING NOT NULL,
    participant_id STRING NOT NULL,
    scan_date DATE NOT NULL,
    whole_brain_volume_cm3 FLOAT64 NOT NULL,
    hippocampal_volume_left_mm3 FLOAT64 NOT NULL,
    hippocampal_volume_right_mm3 FLOAT64 NOT NULL,
    entorhinal_cortex_thickness_mm FLOAT64 NOT NULL,
    white_matter_hyperintensities_cm3 FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS `spoke_local_neurology.clinical_trial_registry` (
    enrollment_id STRING NOT NULL,
    participant_id STRING NOT NULL,
    trial_arm STRING NOT NULL,
    cohort_type STRING NOT NULL,
    baseline_abeta_42 FLOAT64 NOT NULL,
    baseline_ptau_181 FLOAT64 NOT NULL,
    apoe_genotype STRING NOT NULL,
    active_trial_status STRING NOT NULL
);
