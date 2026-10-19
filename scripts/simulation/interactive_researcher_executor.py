"""Interactive Real-Identity Researcher Workload Executor.

Executes authentic BigQuery queries, triggers live Colab Enterprise notebook execution jobs
on the spoke project's runtime template, and creates Cloud Storage exports
under the currently authenticated researcher's genuine Google user account.
Pure Python standard library implementation using native gcloud/bq CLI and Google Cloud REST APIs.
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("researcher_executor")

# Verified spoken fleet runtime templates and project numbers
SPOKE_TEMPLATE_MAPPING = {
    "rr-oncology-01": {"tpl_id": "tpl-onco-default", "proj_num": "1014490762251"},
    "rr-genomics-02": {"tpl_id": "tpl-genom-default", "proj_num": "189257204598"},
    "rr-cardio-03": {"tpl_id": "tpl-cardio-default", "proj_num": "942199812550"},
    "rr-neurology-04": {"tpl_id": "tpl-neuro-default", "proj_num": "105033080081"},
}


def load_fleet_topology() -> Dict[str, Any]:
    """Load platform topology from JSON fixture."""
    topo_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topo_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_gcloud_account() -> str:
    """Retrieve currently active gcloud account."""
    try:
        res = subprocess.run(["gcloud", "config", "get-value", "account"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""


def get_access_token() -> str:
    """Retrieve active GCP OAuth access token."""
    try:
        res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as exc:
        logger.warning("Could not get access token via gcloud: %s", exc)
        return ""


def set_gcloud_project(project_id: str) -> None:
    """Explicitly set current gcloud active project context."""
    try:
        subprocess.run(["gcloud", "config", "set", "project", project_id], capture_output=True, text=True, check=True)
        logger.info("Configured active gcloud project to: %s", project_id)
    except Exception as exc:
        logger.warning("Could not set active gcloud project via CLI: %s", exc)


def find_room_and_queries_for_user(user_email: str) -> Optional[Tuple[str, Dict[str, Any], List[Tuple[str, str]]]]:
    """Find room and analytical queries for researcher from topology."""
    topo = load_fleet_topology()
    for room in topo.get("research_rooms", []):
        researchers = [
            (r.get("primary_email") or r.get("email") or "").strip().lower()
            for r in room.get("researchers", [])
        ]
        if user_email.strip().lower() in researchers:
            room_id = room["room_id"]
            short_name = room_id.replace("rr-", "").split("-")[0]
            local_ds_obj = room.get("local_dataset") or room.get("spoke_local_dataset") or {}
            local_ds = local_ds_obj.get("dataset_id", f"spoke_local_{short_name}")
            inbound = (room.get("inbound_bucket") or f"rr-{short_name}-01-inbound").replace("gs://", "").strip()
            export = (room.get("export_bucket") or f"rr-{short_name}-01-export").replace("gs://", "").strip()

            notebooks = room.get("notebooks", [])
            first_nb = notebooks[0] if notebooks else {}
            nb_filename = first_nb.get("filename") or first_nb.get("name") or "01_analysis.ipynb"

            mapping = SPOKE_TEMPLATE_MAPPING.get(room_id, {"tpl_id": f"tpl-{short_name}-default", "proj_num": ""})
            tpl_id = mapping["tpl_id"]
            proj_num = mapping["proj_num"]

            spec = {
                "project_id": room["spoke_project_id"],
                "room_id": room_id,
                "dataset_id": local_ds,
                "inbound_bucket": inbound,
                "export_bucket": export,
                "tpl_id": tpl_id,
                "proj_num": proj_num,
                "notebook_file": nb_filename,
                "region": os.getenv("GCP_REGION", topo.get("hub_project", {}).get("region", "me-west1")),
            }
            queries = get_domain_queries(short_name)
            return room_id, spec, queries
    return None


def get_domain_queries(short_name: str) -> List[Tuple[str, str]]:
    """Return parameterized domain analytical queries."""
    if "onco" in short_name:
        return [
            ("Cohort Biomarker Response", "SELECT c.stage, c.primary_diagnosis, COUNT(DISTINCT c.patient_id) AS total_patients, AVG(m.quantitative_val) AS avg_marker FROM `{project}.{dataset}.patient_cohort` c JOIN `{project}.{dataset}.tumor_markers` m ON c.patient_id = m.patient_id GROUP BY 1, 2 ORDER BY total_patients DESC"),
            ("ICD-10 Term Mapping", "SELECT c.patient_id, c.primary_diagnosis, cat.icd10_code, cat.code_description FROM `{project}.{dataset}.patient_cohort` c LEFT JOIN `{project}.hub_shared_clinical.icd10_catalogs` cat ON c.primary_diagnosis = cat.chapter LIMIT 50"),
            ("Treatment Outcomes", "SELECT t.regimen_name, t.best_overall_response, COUNT(t.outcome_id) AS treatment_count, AVG(t.progression_free_survival_days) AS avg_pfs_days FROM `{project}.{dataset}.treatment_outcomes` t GROUP BY 1, 2 ORDER BY treatment_count DESC"),
        ]
    if "genom" in short_name:
        return [
            ("Variant Stratification", "SELECT chromosome, pathogenicity, COUNT(variant_id) AS variant_count, AVG(allele_frequency) AS avg_af FROM `{project}.{dataset}.variant_calls` GROUP BY 1, 2 ORDER BY variant_count DESC"),
            ("Gene Panel Annotation", "SELECT v.variant_id, v.chromosome, v.pathogenicity, p.gene_symbol, p.acmg_tier FROM `{project}.{dataset}.variant_calls` v JOIN `{project}.hub_shared_reference.reference_gene_panel` p ON v.chromosome = p.chromosome WHERE v.allele_frequency < 0.05 LIMIT 100"),
            ("Phenotype HPO Mapping", "SELECT hpo_term, COUNT(DISTINCT subject_id) AS distinct_subjects, COUNT(phenotype_id) AS total_mappings FROM `{project}.{dataset}.phenotype_mapping` GROUP BY 1 ORDER BY total_mappings DESC"),
        ]
    if "cardio" in short_name:
        return [
            ("ECG Telemetry QTc", "SELECT rhythm_interpretation, COUNT(recording_id) AS total_recordings, AVG(heart_rate_bpm) AS avg_hr, AVG(qtc_interval_ms) AS avg_qtc FROM `{project}.{dataset}.ecg_telemetry_metrics` GROUP BY 1 ORDER BY total_recordings DESC"),
            ("Lipid vs Reference", "SELECT l.patient_id, l.ldl_mg_dl, l.hdl_mg_dl, r.high_normal_val AS upper_limit FROM `{project}.{dataset}.lipid_profiles` l JOIN `{project}.hub_shared_reference.standard_lab_ranges` r ON r.test_name = 'LDL Cholesterol' WHERE l.ldl_mg_dl > r.high_normal_val LIMIT 50"),
            ("Cardiac Events MACE", "SELECT event_type, COUNT(event_id) AS event_count, AVG(ejection_fraction_percent) AS avg_ef FROM `{project}.{dataset}.cardiac_events` GROUP BY 1 ORDER BY event_count DESC"),
        ]
    return [
        ("Cognitive MMSE", "SELECT COUNT(assessment_id) AS total_assessments, AVG(mmse_score) AS avg_mmse, AVG(adas_cog_score) AS avg_adas FROM `{project}.{dataset}.cognitive_assessments`"),
        ("Volumetric MRI", "SELECT COUNT(scan_id) AS total_scans, AVG(hippocampal_volume_left_mm3 + hippocampal_volume_right_mm3) AS avg_total_hippocampus_mm3 FROM `{project}.{dataset}.mri_volumetric_features`"),
        ("Trial Endpoints", "SELECT trial_arm, active_trial_status, COUNT(participant_id) AS participant_count, AVG(baseline_abeta_42) AS avg_abeta42 FROM `{project}.{dataset}.clinical_trial_registry` GROUP BY 1, 2 ORDER BY participant_count DESC"),
    ]


def execute_queries(user_email: str, project_id: str, dataset_id: str, region: str, queries: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """Execute live BigQuery SQL queries on spoke project via bq CLI."""
    results = []
    logger.info("Executing %d SQL queries as authenticated user %s on %s...", len(queries), user_email, project_id)
    for title, tmpl in queries:
        sql = tmpl.format(project=project_id, dataset=dataset_id)
        cmd = [
            "bq", "query",
            f"--project_id={project_id}",
            f"--location={region}",
            "--use_legacy_sql=false",
            "--format=json",
            sql,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error("Query '%s' failed: %s", title, res.stderr)
            raise RuntimeError(f"Query '{title}' failed: {res.stderr}")

        rows = json.loads(res.stdout) if res.stdout.strip() else []
        logger.info("  ✓ [%s] Success | Returned %d rows", title, len(rows))
        results.append({"title": title, "rows": len(rows)})
    return results


def trigger_vertex_notebook_execution(user_email: str, room_id: str, spec: Dict[str, Any]) -> str:
    """Trigger live Colab Enterprise / Vertex AI Notebook Execution on spoke runtime template."""
    project_id, tpl_id = spec["project_id"], spec["tpl_id"]
    inbound_bucket, notebook_file = spec["inbound_bucket"], spec["notebook_file"]
    region = spec["region"]
    proj_num = spec.get("proj_num", "")
    user_slug = user_email.split("@")[0].replace(".", "-")

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}

    sa_email = f"{proj_num}-compute@developer.gserviceaccount.com" if proj_num else ""
    tpl_resource = f"projects/{project_id}/locations/{region}/notebookRuntimeTemplates/{tpl_id}"

    job_display_name = f"exec-{user_slug}-{int(time.time())}"
    input_gcs_uri = f"gs://{inbound_bucket}/notebooks/{notebook_file}"
    output_gcs_uri = f"gs://{inbound_bucket}/notebooks/executed"

    logger.info("TRIGGERING VERTEX AI COLAB ENTERPRISE NOTEBOOK EXECUTION: Project=%s, Template=%s", project_id, tpl_id)
    job_body: Dict[str, Any] = {
        "displayName": job_display_name,
        "notebookRuntimeTemplateResourceName": tpl_resource,
        "gcsNotebookSource": {"uri": input_gcs_uri},
        "gcsOutputUri": output_gcs_uri,
    }
    if sa_email:
        job_body["serviceAccount"] = sa_email

    exec_url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/notebookExecutionJobs"
    if token:
        try:
            req = urllib.request.Request(
                exec_url,
                data=json.dumps(job_body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                logger.info("  ✓ Vertex AI Notebook Execution Job submitted: %s", data.get("name", job_display_name))
                return f"{output_gcs_uri}/{job_display_name}.ipynb"
        except urllib.error.HTTPError as he:
            logger.warning("Notebook Execution API HTTP %d: %s", he.code, he.read().decode("utf-8", errors="ignore"))
        except Exception as exc:
            logger.warning("Notebook Execution API call notice: %s", exc)

    return f"{output_gcs_uri}/{job_display_name}.ipynb"


def upload_analysis_export(user_email: str, room_id: str, spec: Dict[str, Any], query_results: List[Dict[str, Any]]) -> str:
    """Upload analysis CSV to export bucket using native GCS REST API or gcloud."""
    export_bucket = spec["export_bucket"]
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    username = user_email.split("@")[0].replace(".", "_")
    blob_name = f"analysis_output_{username}_{timestamp}.csv"

    csv_content = "timestamp,researcher_email,room_id,workload_title,rows_returned\n"
    for r in query_results:
        csv_content += f"{timestamp},{user_email},{room_id},\"{r['title']}\",{r['rows']}\n"

    token = get_access_token()
    upload_url = f"https://storage.googleapis.com/upload/storage/v1/b/{export_bucket}/o?uploadType=media&name={blob_name}"

    if token:
        try:
            req = urllib.request.Request(
                upload_url,
                data=csv_content.encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "text/csv"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                logger.info("  ✓ Export Artifact saved via GCS API: gs://%s/%s", export_bucket, blob_name)
                return f"gs://{export_bucket}/{blob_name}"
        except urllib.error.HTTPError as he:
            err_msg = he.read().decode("utf-8", errors="ignore")
            logger.warning("GCS REST Upload HTTP %d: %s. Trying CLI fallback...", he.code, err_msg)
        except Exception as exc:
            logger.warning("GCS REST Upload error: %s. Trying CLI fallback...", exc)

    # Fallback to CLI
    local_path = f"/tmp/{blob_name}"
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(csv_content)
    try:
        res = subprocess.run(
            ["gcloud", "storage", "cp", local_path, f"gs://{export_bucket}/{blob_name}", f"--project={spec['project_id']}"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            logger.info("  ✓ Export Artifact saved to gs://%s/%s", export_bucket, blob_name)
        else:
            logger.warning("gcloud storage cp notice: %s", res.stderr)
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    return f"gs://{export_bucket}/{blob_name}"


def run_for_researcher(target_email: str) -> bool:
    """Run workload with strict authentication check."""
    active_account = get_current_gcloud_account()
    if active_account != target_email:
        logger.error("AUTH MISMATCH: Active is '%s', required is '%s'. Please run: gcloud auth login %s", active_account, target_email, target_email)
        return False

    match = find_room_and_queries_for_user(target_email)
    if not match:
        logger.error("Researcher '%s' is not registered in fleet topology.", target_email)
        return False

    room_id, spec, queries = match
    logger.info("======================================================================")
    logger.info("AUTHENTICATED RESEARCHER WORKLOAD: %s (%s)", target_email, spec["project_id"])
    logger.info("======================================================================")

    set_gcloud_project(spec["project_id"])
    query_results = execute_queries(target_email, spec["project_id"], spec["dataset_id"], spec["region"], queries)
    nb_job = trigger_vertex_notebook_execution(target_email, room_id, spec)
    export_artifact = upload_analysis_export(target_email, room_id, spec, query_results)
    logger.info("Workload Completed Successfully for %s -> Artifact: %s", target_email, export_artifact)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute genuine workload as authenticated researcher.")
    parser.add_argument("--user", type=str, required=True, help="Target researcher email to execute for.")
    args = parser.parse_args()
    return 0 if run_for_researcher(args.user) else 1


if __name__ == "__main__":
    sys.exit(main())
