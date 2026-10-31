"""Researcher Live Workload Runner for CloudShell / Local GCP Execution.

Executed by or on behalf of logged-in researchers to generate authentic GCP billing,
BigQuery job execution history in INFORMATION_SCHEMA, Cloud Audit Logs, and Storage bucket outputs.

Usage:
  # Run for currently authenticated gcloud / CloudShell user:
  python3 scripts/run_researcher_workload.py

  # Run for a specific researcher profile:
  python3 scripts/run_researcher_workload.py --user prof.miriam.levy@example-tre.org

  # Run all researcher workloads sequentially across all 4 rooms:
  python3 scripts/run_researcher_workload.py --all
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import argparse
import datetime
import io
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
from google.cloud import bigquery, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("researcher_workload")

REGION = os.getenv("GCP_REGION", "me-west1")

ROOM_PROFILES: Dict[str, Dict[str, Any]] = {
    "rr-oncology-01": {
        "project_id": "gcp-rr-spoke-oncology-01",
        "dataset_id": "spoke_local_oncology",
        "export_bucket": "rr-oncology-01-export",
        "researchers": [
            "dr.oren.katz@example-tre.org",
            "prof.miriam.levy@example-tre.org",
        ],
        "queries": [
            (
                "Cohort Biomarker Response Analysis",
                "SELECT c.stage, c.primary_diagnosis, COUNT(DISTINCT c.patient_id) AS total_patients, "
                "AVG(m.quantitative_val) AS avg_marker, MAX(m.quantitative_val) AS max_marker "
                "FROM `{project}.{dataset}.patient_cohort` c "
                "JOIN `{project}.{dataset}.tumor_markers` m ON c.patient_id = m.patient_id "
                "GROUP BY 1, 2 ORDER BY total_patients DESC",
            ),
            (
                "Cross-Dataset ICD-10 Clinical Term Mapping",
                "SELECT c.patient_id, c.primary_diagnosis, cat.icd10_code, cat.code_description "
                "FROM `{project}.{dataset}.patient_cohort` c "
                "LEFT JOIN `{project}.hub_shared_clinical.icd10_catalogs` cat ON c.primary_diagnosis = cat.chapter "
                "LIMIT 50",
            ),
            (
                "Treatment Outcome & Response Rate Evaluation",
                "SELECT t.regimen_name, t.best_overall_response, COUNT(t.outcome_id) AS treatment_count, "
                "AVG(t.progression_free_survival_days) AS avg_pfs_days "
                "FROM `{project}.{dataset}.treatment_outcomes` t "
                "GROUP BY 1, 2 ORDER BY treatment_count DESC",
            ),
        ],
    },
    "rr-genomics-02": {
        "project_id": "gcp-rr-spoke-genomics-02",
        "dataset_id": "spoke_local_genomics",
        "export_bucket": "rr-genomics-02-export",
        "researchers": [
            "dr.eitan.rosen@example-tre.org",
            "prof.anat.shapiro@example-tre.org",
        ],
        "queries": [
            (
                "Pathogenic Variant Frequency Stratification",
                "SELECT chromosome, pathogenicity, COUNT(variant_id) AS variant_count, "
                "AVG(allele_frequency) AS avg_af, AVG(depth) AS avg_depth "
                "FROM `{project}.{dataset}.variant_calls` "
                "GROUP BY 1, 2 ORDER BY variant_count DESC",
            ),
            (
                "Cross-Dataset ACMG Gene Panel Annotation",
                "SELECT v.variant_id, v.chromosome, v.pathogenicity, p.gene_symbol, p.acmg_tier, p.disease_association "
                "FROM `{project}.{dataset}.variant_calls` v "
                "JOIN `{project}.hub_shared_reference.reference_gene_panel` p ON v.chromosome = p.chromosome "
                "WHERE v.allele_frequency < 0.05 LIMIT 100",
            ),
            (
                "Phenotypic HPO Term Sample Mapping",
                "SELECT hpo_term, COUNT(DISTINCT subject_id) AS distinct_subjects, COUNT(phenotype_id) AS total_mappings "
                "FROM `{project}.{dataset}.phenotype_mapping` GROUP BY 1 ORDER BY total_mappings DESC",
            ),
        ],
    },
    "rr-cardio-03": {
        "project_id": "gcp-rr-spoke-cardio-03",
        "dataset_id": "spoke_local_cardio",
        "export_bucket": "rr-cardio-03-export",
        "researchers": [
            "dr.maya.lin@example-tre.org",
            "dr.daniel.cohen@example-tre.org",
        ],
        "queries": [
            (
                "ECG Telemetry QTc Anomaly Stratification",
                "SELECT rhythm_interpretation, COUNT(recording_id) AS total_recordings, "
                "AVG(heart_rate_bpm) AS avg_hr, AVG(qtc_interval_ms) AS avg_qtc, "
                "COUNTIF(qtc_interval_ms > 460) AS prolonged_qtc_count "
                "FROM `{project}.{dataset}.ecg_telemetry_metrics` GROUP BY 1 ORDER BY total_recordings DESC",
            ),
            (
                "Lipid Profile vs Standard Reference Ranges",
                "SELECT l.patient_id, l.ldl_mg_dl, l.hdl_mg_dl, r.high_normal_val AS upper_limit "
                "FROM `{project}.{dataset}.lipid_profiles` l "
                "JOIN `{project}.hub_shared_reference.standard_lab_ranges` r ON r.test_name = 'LDL Cholesterol' "
                "WHERE l.ldl_mg_dl > r.high_normal_val LIMIT 50",
            ),
            (
                "Major Adverse Cardiac Event (MACE) Summary",
                "SELECT event_type, COUNT(event_id) AS event_count, AVG(ejection_fraction_percent) AS avg_ef "
                "FROM `{project}.{dataset}.cardiac_events` GROUP BY 1 ORDER BY event_count DESC",
            ),
        ],
    },
    "rr-neurology-04": {
        "project_id": "gcp-rr-spoke-neurology-04",
        "dataset_id": "spoke_local_neurology",
        "export_bucket": "rr-neurology-04-export",
        "researchers": [
            "dr.noa.shapira@example-tre.org",
            "dr.rami.friedman@example-tre.org",
        ],
        "queries": [
            (
                "Cognitive Assessment & MMSE Trajectory",
                "SELECT COUNT(assessment_id) AS total_assessments, AVG(mmse_score) AS avg_mmse, "
                "AVG(adas_cog_score) AS avg_adas, AVG(cdr_sum_of_boxes) AS avg_cdr "
                "FROM `{project}.{dataset}.cognitive_assessments`",
            ),
            (
                "Volumetric MRI Hippocampal Atrophy Correlation",
                "SELECT COUNT(scan_id) AS total_scans, "
                "AVG(hippocampal_volume_left_mm3 + hippocampal_volume_right_mm3) AS avg_total_hippocampus_mm3, "
                "AVG(whole_brain_volume_cm3) AS avg_brain_cm3 "
                "FROM `{project}.{dataset}.mri_volumetric_features`",
            ),
            (
                "Trial Phase 2 Endpoint Trajectory",
                "SELECT trial_arm, active_trial_status, COUNT(participant_id) AS participant_count, "
                "AVG(baseline_abeta_42) AS avg_abeta42, AVG(baseline_ptau_181) AS avg_ptau181 "
                "FROM `{project}.{dataset}.clinical_trial_registry` GROUP BY 1, 2 ORDER BY participant_count DESC",
            ),
        ],
    },
}


def get_current_user_email() -> str:
    """Detect authenticated gcloud user account."""
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "account"],
            capture_output=True,
            text=True,
            check=True,
        )
        email = res.stdout.strip()
        if email and "@" in email:
            return email
    except Exception:
        pass
    return "prof.miriam.levy@example-tre.org"


def find_room_for_user(user_email: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Find research room matching researcher email."""
    for room_id, spec in ROOM_PROFILES.items():
        if user_email in spec["researchers"]:
            return room_id, spec
    return None


def execute_researcher_queries(
    user_email: str,
    room_id: str,
    spec: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Execute live BigQuery SQL queries on spoke project with researcher labels."""
    project_id = spec["project_id"]
    dataset_id = spec["dataset_id"]
    client = bigquery.Client(project=project_id, location=REGION)

    results_summary = []
    logger.info("Executing BigQuery Workload on %s as researcher %s...", project_id, user_email)

    for title, query_tmpl in spec["queries"]:
        sql = query_tmpl.format(project=project_id, dataset=dataset_id).strip()
        job_config = bigquery.QueryJobConfig(
            labels={
                "researcher": user_email.split("@")[0].replace(".", "_"),
                "room_id": room_id.replace("-", "_"),
                "workload_type": "analytical_workload",
            }
        )
        query_job = client.query(sql, job_config=job_config)
        rows = list(query_job.result())
        bytes_billed = query_job.total_bytes_billed or 0

        logger.info(
            "  -> Query '%s': Job %s completed | Rows: %d | Bytes Billed: %d",
            title,
            query_job.job_id,
            len(rows),
            bytes_billed,
        )
        results_summary.append({
            "title": title,
            "job_id": query_job.job_id,
            "row_count": len(rows),
            "bytes_billed": bytes_billed,
        })

    return results_summary


def write_export_output(
    user_email: str,
    room_id: str,
    spec: Dict[str, Any],
    query_results: List[Dict[str, Any]],
) -> str:
    """Generate real analysis CSV summary in spoke export bucket."""
    bucket_name = spec["export_bucket"]
    storage_client = storage.Client(project=spec["project_id"])
    bucket = storage_client.bucket(bucket_name)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    username = user_email.split("@")[0]
    blob_name = f"analysis_output_{username}_{timestamp}.csv"

    csv_buf = io.StringIO()
    csv_buf.write("analysis_timestamp,researcher,room_id,workload_title,job_id,rows_analyzed,bytes_billed\n")
    for r in query_results:
        csv_buf.write(
            f"{timestamp},{user_email},{room_id},\"{r['title']}\",{r['job_id']},{r['row_count']},{r['bytes_billed']}\n"
        )

    blob = bucket.blob(blob_name)
    blob.upload_from_string(csv_buf.getvalue(), content_type="text/csv")
    logger.info("Uploaded output to spoke export bucket: gs://%s/%s", bucket_name, blob_name)
    return f"gs://{bucket_name}/{blob_name}"


def run_workload_for_user(user_email: str) -> bool:
    """Run full organic workload for a single researcher."""
    match = find_room_for_user(user_email)
    if not match:
        logger.error("User '%s' is not registered to any active research room.", user_email)
        return False

    room_id, spec = match
    logger.info("======================================================================")
    logger.info("RESEARCHER WORKLOAD EXECUTION: %s (%s)", user_email, room_id)
    logger.info("Target Spoke Project: %s | Location: %s", spec["project_id"], REGION)
    logger.info("======================================================================")

    query_results = execute_researcher_queries(user_email, room_id, spec)
    output_gcs = write_export_output(user_email, room_id, spec, query_results)

    logger.info("Researcher Workload Completed for %s -> Artifact: %s", user_email, output_gcs)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live organic researcher workload on GCP.")
    parser.add_argument("--user", type=str, help="Specific researcher email to execute workload for.")
    parser.add_argument("--all", action="store_true", help="Execute workloads sequentially for all 8 researchers.")
    args = parser.parse_args()

    if args.all:
        logger.info("Executing live workloads for all 8 researchers across all 4 rooms...")
        all_success = True
        for room_id, spec in ROOM_PROFILES.items():
            for researcher in spec["researchers"]:
                success = run_workload_for_user(researcher)
                if not success:
                    all_success = False
        return 0 if all_success else 1

    user_email = args.user or get_current_user_email()
    success = run_workload_for_user(user_email)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
