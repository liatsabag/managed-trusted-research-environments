"""Target Fleet Resource Specifications and Constants for GCP Verification."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import os

REGION = os.getenv("GCP_REGION", "me-west1")
ADMIN_DOMAIN = os.getenv("ADMIN_DOMAIN", "liatsabag.altostrat.com")
HUB_PROJECT_ID = os.getenv("HUB_PROJECT_ID", "gcp-rr-hub-core")

SPOKE_PROJECTS = {
    "gcp-rr-spoke-oncology-01": {
        "room_id": "rr-oncology-01",
        "datasets": {
            "spoke_local_oncology": {
                "patient_cohort": 650,
                "tumor_markers": 1000,
                "treatment_outcomes": 450,
                "immunotherapy_response": 300,
            }
        },
        "linked_datasets": ["hub_shared_clinical", "hub_shared_reference"],
        "buckets": {
            "rr-oncology-01-inbound": [
                "baseline_demographics.csv",
                "lab_observations.csv",
                "tumor_panel_mutations.csv",
                "treatment_history.csv",
                "notebooks/01_exploratory_cohort_analysis.ipynb",
                "notebooks/02_statistical_risk_model.ipynb",
            ],
            "rr-oncology-01-export": ["candidate_survival_summary.csv"],
        },
        "group": f"tre-onco-researchers@{ADMIN_DOMAIN}",
        "users": [f"dr.oren.katz@{ADMIN_DOMAIN}", f"prof.miriam.levy@{ADMIN_DOMAIN}"],
    },
    "gcp-rr-spoke-genomics-02": {
        "room_id": "rr-genomics-02",
        "datasets": {
            "spoke_local_genomics": {
                "variant_calls": 1000,
                "sample_manifests": 200,
                "phenotype_mapping": 500,
            }
        },
        "linked_datasets": ["hub_shared_clinical", "hub_shared_reference"],
        "buckets": {
            "rr-genomics-02-inbound": [
                "sample_metadata.csv",
                "pathogenic_variants.csv",
                "phenotype_hpo_terms.csv",
                "notebooks/01_variant_qc_and_filtering.ipynb",
                "notebooks/02_pathogenicity_clustering.ipynb",
            ],
            "rr-genomics-02-export": ["rare_variant_frequency_report.csv"],
        },
        "group": f"tre-genom-researchers@{ADMIN_DOMAIN}",
        "users": [f"dr.eitan.rosen@{ADMIN_DOMAIN}", f"prof.anat.shapiro@{ADMIN_DOMAIN}"],
    },
    "gcp-rr-spoke-cardio-03": {
        "room_id": "rr-cardio-03",
        "datasets": {
            "spoke_local_cardio": {
                "ecg_telemetry_metrics": 800,
                "lipid_profiles": 600,
                "patient_registry": 400,
                "cardiac_events": 250,
            }
        },
        "linked_datasets": ["hub_shared_clinical", "hub_shared_reference"],
        "buckets": {
            "rr-cardio-03-inbound": [
                "cardiac_registry.csv",
                "lipid_telemetry.csv",
                "ecg_waveform_features.csv",
                "notebooks/01_telemetry_feature_extraction.ipynb",
                "notebooks/02_framingham_risk_model.ipynb",
            ],
            "rr-cardio-03-export": ["mace_prediction_findings.csv"],
        },
        "group": f"tre-cardio-researchers@{ADMIN_DOMAIN}",
        "users": [f"dr.maya.lin@{ADMIN_DOMAIN}", f"dr.daniel.cohen@{ADMIN_DOMAIN}"],
    },
    "gcp-rr-spoke-neurology-04": {
        "room_id": "rr-neurology-04",
        "datasets": {
            "spoke_local_neurology": {
                "cognitive_assessments": 550,
                "mri_volumetric_features": 350,
                "clinical_trial_registry": 200,
            }
        },
        "linked_datasets": ["hub_shared_clinical", "hub_shared_reference"],
        "buckets": {
            "rr-neurology-04-inbound": [
                "cognitive_scores.csv",
                "mri_cortical_thickness.csv",
                "csf_biomarkers.csv",
                "notebooks/01_volumetric_mri_analysis.ipynb",
                "notebooks/02_biomarker_correlation.ipynb",
            ],
            "rr-neurology-04-export": ["trial_phase2_endpoints.csv"],
        },
        "group": f"tre-neuro-researchers@{ADMIN_DOMAIN}",
        "users": [f"dr.noa.shapira@{ADMIN_DOMAIN}", f"dr.rami.friedman@{ADMIN_DOMAIN}"],
    },
}

EXPECTED_HUB_DATASETS = {
    "hub_registry": {
        "reg_institutes": 4,
        "reg_research_rooms": 4,
        "reg_researchers": 8,
        "reg_room_packages": 36,
    },
    "hub_telemetry": {
        "ops_regulatory_checklist": 20,
        "ops_room_requests": 2,
        "ops_airlock_requests": 4,
        "ops_audit_logs": 32,
        "view_billing_export": "VIEW",
    },
    "hub_shared_clinical": {
        "icd10_catalogs": 500,
        "omop_vocabulary": 800,
    },
    "hub_shared_reference": {
        "reference_gene_panel": 250,
        "standard_lab_ranges": 150,
    },
}

EXPECTED_HUB_BUCKETS = {
    "gcp-rr-hub-approvals": {
        "rr-oncology-01": ["research_protocol_approval.txt", "helsinki_irb_approval.txt", "data_transfer_approval.txt", "extraction_protocol_approval.txt", "dua_approval.txt"],
        "rr-genomics-02": ["research_protocol_approval.txt", "helsinki_irb_approval.txt", "data_transfer_approval.txt", "extraction_protocol_approval.txt", "dua_approval.txt"],
        "rr-cardio-03": ["research_protocol_approval.txt", "helsinki_irb_approval.txt", "data_transfer_approval.txt", "extraction_protocol_approval.txt", "dua_approval.txt"],
        "rr-neurology-04": ["research_protocol_approval.txt", "helsinki_irb_approval.txt", "data_transfer_approval.txt", "extraction_protocol_approval.txt", "dua_approval.txt"],
        "rr-immunology-05": ["research_protocol_approval.txt", "helsinki_irb_approval.txt", "extraction_protocol_approval.txt", "dua_approval.txt"],
        "rr-pediatrics-06": ["research_protocol_approval.txt", "helsinki_irb_approval.txt", "data_transfer_approval.txt", "extraction_protocol_approval.txt", "dua_approval.txt"],
    }
}

EXPECTED_GROUPS = [
    f"tre-onco-researchers@{ADMIN_DOMAIN}",
    f"tre-genom-researchers@{ADMIN_DOMAIN}",
    f"tre-cardio-researchers@{ADMIN_DOMAIN}",
    f"tre-neuro-researchers@{ADMIN_DOMAIN}",
]

EXPECTED_USERS = [
    f"dr.oren.katz@{ADMIN_DOMAIN}",
    f"prof.miriam.levy@{ADMIN_DOMAIN}",
    f"dr.eitan.rosen@{ADMIN_DOMAIN}",
    f"prof.anat.shapiro@{ADMIN_DOMAIN}",
    f"dr.maya.lin@{ADMIN_DOMAIN}",
    f"dr.daniel.cohen@{ADMIN_DOMAIN}",
    f"dr.noa.shapira@{ADMIN_DOMAIN}",
    f"dr.rami.friedman@{ADMIN_DOMAIN}",
]

REQUIRED_SPOKE_ROLES = [
    "roles/bigquery.jobUser",
    "roles/bigquery.dataEditor",
    "roles/storage.objectAdmin",
    "roles/aiplatform.user",
    "roles/notebooks.runner",
]
