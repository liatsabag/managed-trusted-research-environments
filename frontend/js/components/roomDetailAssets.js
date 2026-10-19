/**
 * Room Asset Metadata & Grounded Specifications
 * Maps specific BigQuery tables, storage files, and research notebooks per room
 */

export const ROOM_ASSET_METADATA = {
  "rr-oncology-01": {
    tables: ["patient_cohort", "tumor_markers", "immunotherapy_response", "treatment_outcomes"],
    compute_machine: {
      type: "e2-standard-4",
      specs: "4 vCPUs, 16 GB RAM",
      runtime: "Standard Clinical ML & Biostatistics",
      accelerator: "None (CPU Optimized)"
    },
    inbound_files: [
      { name: "baseline_demographics.csv", size: 31266, desc: "Patient demographics & staging" },
      { name: "lab_observations.csv", size: 38732, desc: "Lab observations & blood chemistry" },
      { name: "treatment_history.csv", size: 26031, desc: "Chemotherapy & immunotherapy history" },
      { name: "tumor_panel_mutations.csv", size: 17537, desc: "Somatic mutation panels & TMB" }
    ],
    export_files: [
      { name: "candidate_survival_summary.csv", size: 207, desc: "Kaplan-Meier survival endpoints" },
      { name: "research_export_dr_oren_katz_20260929.csv", size: 136, desc: "De-identified aggregated findings" }
    ],
    notebooks: [
      { name: "01_exploratory_cohort_analysis.ipynb", desc: "Cohort stratification & Kaplan-Meier survival curves", status: "Executed", runs: 12 },
      { name: "02_statistical_risk_model.ipynb", desc: "Cox proportional hazards biomarker regression", status: "Ready", runs: 6 }
    ]
  },
  "rr-cardio-03": {
    tables: ["cardiac_events", "ecg_telemetry_metrics", "lipid_profiles", "patient_registry"],
    compute_machine: {
      type: "e2-standard-2",
      specs: "2 vCPUs, 8 GB RAM",
      runtime: "R Epidemiology & Bioconductor Workspace",
      accelerator: "None (CPU Optimized)"
    },
    inbound_files: [
      { name: "cardiac_registry.csv", size: 19266, desc: "Longitudinal cardiology cohort" },
      { name: "ecg_waveform_features.csv", size: 41576, desc: "Extracted 12-lead ECG intervals" },
      { name: "lipid_telemetry.csv", size: 29100, desc: "Lipid panel time-series" }
    ],
    export_files: [
      { name: "mace_prediction_findings.csv", size: 236, desc: "Major adverse cardiac event predictions" }
    ],
    notebooks: [
      { name: "01_telemetry_feature_extraction.ipynb", desc: "Waveform feature engineering & filtering", status: "Executed", runs: 14 },
      { name: "02_framingham_risk_model.ipynb", desc: "Cardiovascular risk score recalibration", status: "Ready", runs: 4 }
    ]
  },
  "rr-genomics-02": {
    tables: ["phenotype_mapping", "sample_manifests", "variant_calls"],
    compute_machine: {
      type: "n2-highmem-8",
      specs: "8 vCPUs, 64 GB RAM",
      runtime: "High-Memory Genomic & Variant Pipeline",
      accelerator: "None (Memory Optimized)"
    },
    inbound_files: [
      { name: "pathogenic_variants.csv", size: 32848, desc: "Filtered genomic SNVs & indels" },
      { name: "phenotype_hpo_terms.csv", size: 26009, desc: "Human Phenotype Ontology mappings" },
      { name: "sample_metadata.csv", size: 10433, desc: "Sequencing depth & quality QC" }
    ],
    export_files: [
      { name: "rare_variant_frequency_report.csv", size: 139, desc: "De-identified allele frequencies" }
    ],
    notebooks: [
      { name: "01_variant_qc_and_filtering.ipynb", desc: "VCF quality scoring & Hardy-Weinberg filter", status: "Executed", runs: 18 },
      { name: "02_pathogenicity_clustering.ipynb", desc: "Clustering of rare pathogenic variants", status: "Ready", runs: 5 }
    ]
  },
  "rr-neurology-04": {
    tables: ["clinical_trial_registry", "cognitive_assessments", "mri_volumetric_features"],
    compute_machine: {
      type: "g2-standard-8",
      specs: "8 vCPUs, 32 GB RAM, 1x NVIDIA L4 (24GB)",
      runtime: "GPU-Accelerated Medical Imaging & Deep Learning",
      accelerator: "NVIDIA L4 24GB VRAM"
    },
    inbound_files: [
      { name: "cognitive_scores.csv", size: 28612, desc: "MMSE and ADAS-Cog evaluation series" },
      { name: "csf_biomarkers.csv", size: 9722, desc: "Amyloid-beta & phosphorylated tau levels" },
      { name: "mri_cortical_thickness.csv", size: 18219, desc: "FreeSurfer cortical parcellations" }
    ],
    export_files: [
      { name: "trial_phase2_endpoints.csv", size: 139, desc: "Cognitive decline endpoint aggregates" }
    ],
    notebooks: [
      { name: "01_volumetric_mri_analysis.ipynb", desc: "Hippocampal volume segmentation regression", status: "Executed", runs: 9 },
      { name: "02_biomarker_correlation.ipynb", desc: "CSF biomarker vs cognitive score modeling", status: "Ready", runs: 3 }
    ]
  }
};
