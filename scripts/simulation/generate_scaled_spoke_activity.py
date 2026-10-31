"""Scaled Spoke Traffic & Activity Generator for GCP Health Data Platform.

Generates authentic researcher activity under each researcher's real authenticated GCP session.
Topology is dynamically resolved from scripts/fixtures/fleet_topology.json.
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import argparse, datetime, json, logging, os, random, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from google.cloud import bigquery, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("gendata")

TOPOLOGY_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
REGION = os.getenv("GCP_REGION", "me-west1")
AI_REGION = os.getenv("VERTEX_AI_REGION", "us-central1")
AI_MODEL = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")

RESEARCHER_WEIGHTS = {
    "dr.oren.katz@example-tre.org": 0.65, "prof.miriam.levy@example-tre.org": 0.35,
    "dr.eitan.rosen@example-tre.org": 0.60, "prof.anat.shapiro@example-tre.org": 0.40,
    "dr.maya.lin@example-tre.org": 0.55, "dr.daniel.cohen@example-tre.org": 0.45,
    "dr.noa.shapira@example-tre.org": 0.70, "dr.rami.friedman@example-tre.org": 0.30,
}


def load_topology() -> Dict[str, Any]:
    with open(TOPOLOGY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_gcloud_account() -> str:
    try:
        return subprocess.run(["gcloud", "config", "get-value", "account"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def set_gcloud_account(account: str) -> None:
    subprocess.run(["gcloud", "config", "set", "account", account], capture_output=True, text=True, check=True)
    logger.info("Active gcloud account switched to: %s", account)


def get_access_token() -> str:
    try:
        return subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception as exc:
        logger.error("Failed to retrieve access token: %s", exc)
        raise


def find_room_for_researcher(topology: Dict[str, Any], user_email: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    for room in topology.get("research_rooms", []):
        for res in room.get("researchers", []):
            if (res.get("primary_email") or res.get("email") or "").strip().lower() == user_email.strip().lower():
                return room, res
    return None


def run_admin_prestep(hub_project: str, dry_run: bool = False) -> Dict[str, Any]:
    """Execute Step 0 Admin queries and GCS uploads to exceed GCP Free Tiers (>1.1 TB BigQuery, >6 GB Storage)."""
    logger.info("STEP 0: ADMIN FREE-TIER EXHAUSTION PRE-STEP (%s)", hub_project)
    results = {"bq_bytes_scanned": 0, "gcs_bytes_uploaded": 0}
    bq_client = bigquery.Client(project=hub_project, location="US")
    large_query = """SELECT datehour, count(1) as total_hits, sum(views) as total_views
    FROM `bigquery-public-data.wikipedia.pageviews_2020` WHERE datehour >= '2020-01-01' AND datehour <= '2020-12-31'
    GROUP BY 1 ORDER BY total_views DESC LIMIT 100"""
    job_config = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=False, labels={"workload": "free_tier_prestep", "role": "admin"})
    query_job = bq_client.query(large_query, job_config=job_config)
    if dry_run:
        results["bq_bytes_scanned"] = query_job.total_bytes_processed or 0
        logger.info("  [DRY-RUN] BigQuery Query would process: %.2f TB", results["bq_bytes_scanned"] / (1024**4))
    else:
        results["bq_bytes_scanned"] = query_job.total_bytes_billed or query_job.total_bytes_processed or 0
        logger.info("  ✓ BigQuery Query Completed | Scanned: %.2f TB", results["bq_bytes_scanned"] / (1024**4))

    gcs_client = storage.Client(project=hub_project)
    target_bucket_name = f"{hub_project}-staging-data"
    if not dry_run:
        try:
            bucket = gcs_client.get_bucket(target_bucket_name)
        except Exception:
            bucket = gcs_client.create_bucket(target_bucket_name, location=REGION)
        sample_chunk = b"0" * (650 * 1024 * 1024)
        for i in range(10):
            blob = bucket.blob(f"freetier_baseline/blob_chunk_{i+1:02d}.dat")
            blob.upload_from_string(sample_chunk, content_type="application/octet-stream")
            results["gcs_bytes_uploaded"] += len(sample_chunk)
            logger.info("  ✓ Uploaded chunk %d/10 (650 MB) to gs://%s/%s", i + 1, target_bucket_name, blob.name)
    else:
        logger.info("  [DRY-RUN] Would upload 10 x 650 MB blobs (6.5 GB total) to gs://%s/", target_bucket_name)
        results["gcs_bytes_uploaded"] = 6500 * 1024 * 1024
    return results


def run_gemini_inference(project_id: str, prompt_text: str, token: str, dry_run: bool = False) -> Dict[str, Any]:
    """Execute live Vertex AI Gemini Flash inference call using available publisher endpoint."""
    if dry_run:
        logger.info("  [DRY-RUN] Gemini inference call on %s: '%s'", project_id, prompt_text[:60] + "...")
        return {"input_tokens": 150, "output_tokens": 500}

    body = {"contents": [{"role": "user", "parts": [{"text": prompt_text}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}}
    encoded_body = json.dumps(body).encode("utf-8")
    for reg, mod in [(AI_REGION, AI_MODEL), ("us-central1", "gemini-2.5-flash"), ("europe-west1", "gemini-2.5-flash")]:
        url = f"https://{reg}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{reg}/publishers/google/models/{mod}:generateContent"
        req = urllib.request.Request(url, data=encoded_body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                usage = data.get("usageMetadata", {})
                logger.info("  ✓ Gemini Completed (%s/%s): %d prompt tokens, %d candidate tokens", reg, mod, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))
                return {"input_tokens": usage.get("promptTokenCount", 0), "output_tokens": usage.get("candidatesTokenCount", 0)}
        except Exception as exc:
            logger.warning("Gemini endpoint %s/%s notice: %s", reg, mod, exc)
    raise RuntimeError(f"All Vertex AI Gemini endpoints failed for {project_id}")


def trigger_colab_runtime_job(project_id: str, room_id: str, template_id: str, notebook_name: str, token: str, dry_run: bool = False) -> str:
    """Trigger Colab Enterprise notebook execution job on spoke runtime template."""
    job_name = f"exec-{room_id}-{int(time.time())}"
    if dry_run:
        logger.info("  [DRY-RUN] Trigger Colab Execution on '%s' (%s) in %s", template_id, notebook_name, project_id)
        return job_name

    url_tpl = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{REGION}/notebookRuntimeTemplates"
    req_tpl = urllib.request.Request(url_tpl, headers={"Authorization": f"Bearer {token}"})
    tpl_resource, service_account = f"projects/{project_id}/locations/{REGION}/notebookRuntimeTemplates/{template_id}", None

    try:
        with urllib.request.urlopen(req_tpl, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for tpl in data.get("notebookRuntimeTemplates", []):
                t_name = tpl.get("name", "")
                if template_id in t_name or not tpl_resource:
                    tpl_resource = t_name
                    parts = t_name.split("/")
                    if len(parts) >= 2 and parts[1].isdigit():
                        service_account = f"{parts[1]}-compute@developer.gserviceaccount.com"
                    break
    except Exception as exc:
        logger.debug("Template lookup notice for %s: %s", project_id, exc)

    url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{REGION}/notebookExecutionJobs"
    body = {
        "displayName": job_name,
        "notebookRuntimeTemplateResourceName": tpl_resource,
        "gcsNotebookSource": {"uri": f"gs://{room_id}-inbound/notebooks/{notebook_name}"},
        "gcsOutputUri": f"gs://{room_id}-inbound/notebooks/executed",
    }
    if service_account:
        body["serviceAccount"] = service_account

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            logger.info("  ✓ Colab Execution Job created: %s (%s)", data.get("name", job_name), notebook_name)
            return data.get("name", job_name)
    except urllib.error.HTTPError as exc:
        err_msg = exc.read().decode("utf-8") if exc.fp else str(exc)
        logger.warning("Colab Execution HTTP %d notice: %s", exc.code, err_msg)
        return job_name
    except Exception as exc:
        logger.warning("Colab Execution notice: %s", exc)
        return job_name


def get_room_queries(room_id: str, spoke: str, count: int) -> List[str]:
    """Generate dynamic randomized analytical SQL queries targeting local and shared hub tables."""
    queries, short = [], ("onco" if "onco" in room_id else ("genom" if "genom" in room_id else ("cardio" if "cardio" in room_id else "neuro")))
    for _ in range(count):
        q = random.randint(1, 5)
        if short == "onco":
            if q == 1:
                queries.append(f"SELECT p.*, t.* FROM `{spoke}.spoke_local_oncology.patient_cohort` p JOIN `{spoke}.spoke_local_oncology.tumor_markers` t ON p.patient_id = t.patient_id WHERE t.quantitative_val > {random.randint(5, 35)}.0")
            elif q == 2:
                queries.append(f"SELECT p.stage, AVG(o.progression_free_survival_days) as avg_pfs, COUNT(DISTINCT p.patient_id) as n_patients FROM `{spoke}.spoke_local_oncology.patient_cohort` p JOIN `{spoke}.spoke_local_oncology.treatment_outcomes` o ON p.patient_id = o.patient_id WHERE o.adverse_event_grade <= {random.randint(1, 4)} GROUP BY p.stage")
            elif q == 3:
                queries.append(f"SELECT p.patient_id, ref.gene_symbol, ref.clinical_significance FROM `{spoke}.spoke_local_oncology.patient_cohort` p CROSS JOIN `{spoke}.hub_shared_reference.reference_gene_panel` ref WHERE p.age > {random.randint(35, 65)} LIMIT {random.randint(30, 80)}")
            elif q == 4:
                queries.append(f"SELECT i.checkpoint_inhibitor, AVG(i.pd_l1_tps_percent) as avg_tps, COUNT(1) as total_resp FROM `{spoke}.spoke_local_oncology.immunotherapy_response` i WHERE i.tmb_score >= {random.randint(5, 20)} GROUP BY 1")
            else:
                queries.append(f"SELECT p.patient_id, p.primary_diagnosis, icd.code_description FROM `{spoke}.spoke_local_oncology.patient_cohort` p JOIN `{spoke}.hub_shared_clinical.icd10_catalogs` icd ON icd.is_valid_clinical_concept = TRUE WHERE p.vital_status = '{random.choice(['ALIVE', 'DECEASED'])}' LIMIT {random.randint(25, 60)}")
        elif short == "genom":
            if q == 1:
                queries.append(f"SELECT v.*, s.mean_coverage FROM `{spoke}.spoke_local_genomics.variant_calls` v JOIN `{spoke}.spoke_local_genomics.sample_manifests` s ON v.sample_id = s.sample_id WHERE v.allele_frequency < {random.uniform(0.01, 0.08):.3f} AND v.depth >= {random.randint(15, 45)}")
            elif q == 2:
                queries.append(f"SELECT hpo_id, COUNT(*) as cnt FROM `{spoke}.spoke_local_genomics.phenotype_mapping` WHERE onset_age_years <= {random.randint(10, 50)} GROUP BY hpo_id ORDER BY cnt DESC LIMIT {random.randint(10, 40)}")
            elif q == 3:
                queries.append(f"SELECT v.chromosome, v.pathogenicity, COUNT(1) as total_variants FROM `{spoke}.spoke_local_genomics.variant_calls` v WHERE v.chromosome = '{random.choice(['chr1', 'chr7', 'chr17', 'chrX', 'chr13'])}' GROUP BY 1, 2")
            elif q == 4:
                queries.append(f"SELECT s.tissue_type, s.sequencing_type, COUNT(1) as sample_cnt FROM `{spoke}.spoke_local_genomics.sample_manifests` s WHERE s.percent_q30 >= {random.uniform(85.0, 95.0):.1f} GROUP BY 1, 2")
            else:
                queries.append(f"SELECT v.variant_id, v.chromosome, ref.gene_symbol FROM `{spoke}.spoke_local_genomics.variant_calls` v JOIN `{spoke}.hub_shared_reference.reference_gene_panel` ref ON v.chromosome = ref.chromosome WHERE v.allele_frequency < {random.uniform(0.02, 0.06):.3f} LIMIT {random.randint(20, 50)}")
        elif short == "cardio":
            if q == 1:
                queries.append(f"SELECT e.*, l.hdl_mg_dl, l.ldl_mg_dl FROM `{spoke}.spoke_local_cardio.ecg_telemetry_metrics` e JOIN `{spoke}.spoke_local_cardio.lipid_profiles` l ON e.patient_id = l.patient_id WHERE l.ldl_mg_dl > {random.randint(110, 160)}")
            elif q == 2:
                queries.append(f"SELECT p.hypertension_history, COUNT(*) as total_events FROM `{spoke}.spoke_local_cardio.patient_registry` p JOIN `{spoke}.spoke_local_cardio.cardiac_events` c ON p.patient_id = c.patient_id WHERE p.age_at_intake >= {random.randint(40, 65)} GROUP BY p.hypertension_history")
            elif q == 3:
                queries.append(f"SELECT e.rhythm_interpretation, AVG(e.qtc_interval_ms) as avg_qtc FROM `{spoke}.spoke_local_cardio.ecg_telemetry_metrics` e WHERE e.heart_rate_bpm BETWEEN {random.randint(50, 70)} AND {random.randint(90, 120)} GROUP BY 1")
            elif q == 4:
                queries.append(f"SELECT c.event_type, c.nyha_class, COUNT(1) as events_cnt FROM `{spoke}.spoke_local_cardio.cardiac_events` c WHERE c.ejection_fraction_percent <= {random.randint(35, 55)} GROUP BY 1, 2")
            else:
                queries.append(f"SELECT l.patient_id, l.total_cholesterol_mg_dl, r.test_name FROM `{spoke}.spoke_local_cardio.lipid_profiles` l CROSS JOIN `{spoke}.hub_shared_reference.standard_lab_ranges` r WHERE l.total_cholesterol_mg_dl >= {random.randint(190, 240)} LIMIT {random.randint(20, 50)}")
        else:
            if q == 1:
                queries.append(f"SELECT c.*, m.entorhinal_cortex_thickness_mm FROM `{spoke}.spoke_local_neurology.cognitive_assessments` c JOIN `{spoke}.spoke_local_neurology.mri_volumetric_features` m ON c.participant_id = m.participant_id WHERE c.mmse_score < {random.randint(20, 26)}")
            elif q == 2:
                queries.append(f"SELECT trial_arm, AVG(mmse_score) as avg_mmse, AVG(adas_cog_score) as avg_adas FROM `{spoke}.spoke_local_neurology.cognitive_assessments` c JOIN `{spoke}.spoke_local_neurology.clinical_trial_registry` r ON c.participant_id = r.participant_id GROUP BY trial_arm")
            elif q == 3:
                queries.append(f"SELECT r.cohort_type, AVG(m.whole_brain_volume_cm3) as avg_brain_vol, AVG(m.white_matter_hyperintensities_cm3) as avg_wmh FROM `{spoke}.spoke_local_neurology.clinical_trial_registry` r JOIN `{spoke}.spoke_local_neurology.mri_volumetric_features` m ON r.participant_id = m.participant_id WHERE r.baseline_abeta_42 <= {random.randint(550, 800)} GROUP BY 1")
            elif q == 4:
                queries.append(f"SELECT r.apoe_genotype, COUNT(1) as participants_cnt FROM `{spoke}.spoke_local_neurology.clinical_trial_registry` r WHERE r.active_trial_status = '{random.choice(['ACTIVE', 'COMPLETED', 'SCREENING'])}' GROUP BY 1")
            else:
                queries.append(f"SELECT c.participant_id, c.mmse_score, icd.code_description FROM `{spoke}.spoke_local_neurology.cognitive_assessments` c CROSS JOIN `{spoke}.hub_shared_clinical.icd10_catalogs` icd WHERE c.mmse_score <= {random.randint(18, 24)} LIMIT {random.randint(20, 50)}")
    return queries


def get_room_ai_prompt(room_id: str) -> str:
    """Generate authentic, randomized domain-specific clinical/genomic AI prompt."""
    if "onco" in room_id:
        prompts = [
            f"Evaluate clinical significance of PD-L1 TPS {random.randint(15, 80)}% and TMB score {random.randint(8, 25)} in stage {random.choice(['III', 'IV'])} adenocarcinoma cohort.",
            f"Assess biomarker prognostic indicators for overall survival in immune checkpoint inhibitor cohort with biomarker value > {random.randint(10, 45)}.",
            f"Correlate actionable ClinVar gene variants with progression-free survival in refractory oncology patients aged {random.randint(45, 75)}+.",
        ]
    elif "genom" in room_id:
        prompts = [
            f"Assess ACMG pathogenicity classification for novel variant on chr{random.choice(['1', '7', '17', 'X'])} with allele frequency {random.uniform(0.001, 0.03):.4f}.",
            f"Analyze whole-genome sequencing mean coverage depth {random.randint(25, 60)}x and phenotype mapping for rare pediatric syndrome.",
            f"Identify high-impact Loss-of-Function mutations in OMOP terminology mapped patient cohort with onset age {random.randint(5, 30)}.",
        ]
    elif "cardio" in room_id:
        prompts = [
            f"Analyze 10-year MACE risk for cohort with LDL {random.randint(140, 195)} mg/dL and prolonged QTc {random.randint(460, 510)} ms under statin therapy.",
            f"Assess ECG telemetry ST-segment changes and NYHA Class {random.choice(['II', 'III', 'IV'])} outcomes across hypertensive registry.",
            f"Correlate lipid telemetry markers total cholesterol {random.randint(210, 290)} mg/dl with adjudicated cardiac ischemic events.",
        ]
    elif "neuro" in room_id:
        prompts = [
            f"Predict cognitive decline trajectory for APOE-{random.choice(['E4/E4', 'E3/E4'])} cohort with baseline MMSE {random.randint(18, 24)} and CSF Abeta42 < 600 pg/mL.",
            f"Analyze entorhinal cortical parcellation thickness {random.uniform(1.8, 3.2):.2f} mm and hippocampal volume loss across clinical trial arms.",
            f"Assess tau PET SUVr biomarker correlation with longitudinal ADAS-Cog score progression in trial arm {random.choice(['Arm-A', 'Arm-B', 'Control'])}.",
        ]
    else:
        prompts = ["Analyze clinical registry cohort demographics and baseline parameters."]
    return random.choice(prompts)


def run_researcher_workload(room: Dict[str, Any], researcher: Dict[str, Any], token: str, scale_factor: float = 1.0, dry_run: bool = False) -> Dict[str, Any]:
    """Execute multi-dimensional workload for a specific researcher under their identity."""
    room_id, spoke_project = room["room_id"], room["spoke_project_id"]
    email = (researcher.get("primary_email") or researcher.get("email") or "").strip()
    short_name = room_id.replace("rr-", "").split("-")[0]
    weight = RESEARCHER_WEIGHTS.get(email, 0.50) * scale_factor
    user_label = email.split("@")[0].replace(".", "_")

    base_queries = int(weight * 12)
    query_count = max(4, base_queries + random.randint(1, 4))
    logger.info("RESEARCHER WORKLOAD: %s (%s) [Weight: %.2f | Target Queries: %d]", email, room_id, weight, query_count)

    bq_client = bigquery.Client(project=spoke_project, location=REGION)
    queries = get_room_queries(room_id, spoke_project, query_count)
    query_stats = []
    for q_idx, sql in enumerate(queries):
        job_config = bigquery.QueryJobConfig(
            dry_run=dry_run,
            use_query_cache=False,
            labels={"researcher": user_label, "room_id": room_id.replace("-", "_"), "workload": "scaled_research_analytics"},
        )
        try:
            job = bq_client.query(sql, job_config=job_config)
            if not dry_run:
                job.result()
            bytes_scanned = (job.total_bytes_processed if dry_run else (job.total_bytes_billed or job.total_bytes_processed)) or 0
            logger.info("  ✓ Query %d/%d %s | Bytes: %d", q_idx + 1, query_count, "[DRY-RUN]" if dry_run else "completed", bytes_scanned)
            query_stats.append({"query_idx": q_idx, "bytes": bytes_scanned})
        except Exception as exc:
            logger.warning("Query notice on %s: %s", spoke_project, exc)

    prompt = get_room_ai_prompt(room_id)
    ai_metrics = run_gemini_inference(spoke_project, prompt, token, dry_run=dry_run)

    available_nbs = [nb.get("filename") for nb in room.get("notebooks", []) if nb.get("filename")]
    notebook_to_run = random.choice(available_nbs) if available_nbs else "01_analysis.ipynb"
    tpl_id = f"tpl-{short_name if short_name != 'neurology' else 'neuro'}-default".replace("oncology", "onco").replace("genomics", "genom")
    colab_job = trigger_colab_runtime_job(spoke_project, room_id, tpl_id, notebook_to_run, token, dry_run=dry_run)

    export_bucket = room.get("export_bucket", f"gs://{room_id}-export").replace("gs://", "")
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    blob_name = f"research_export_{user_label}_{timestamp}.csv"
    csv_payload = f"timestamp,researcher,room_id,weight,queries_run,ai_tokens,notebook\n{timestamp},{email},{room_id},{weight},{len(query_stats)},{ai_metrics.get('output_tokens', 0)},{notebook_to_run}\n"

    if not dry_run:
        storage.Client(project=spoke_project).bucket(export_bucket).blob(blob_name).upload_from_string(csv_payload, content_type="text/csv")
        logger.info("  ✓ Export CSV uploaded: gs://%s/%s", export_bucket, blob_name)
    else:
        logger.info("  [DRY-RUN] Would upload export CSV to gs://%s/%s", export_bucket, blob_name)

    return {"researcher": email, "room_id": room_id, "queries_completed": len(query_stats), "ai_metrics": ai_metrics, "colab_job": colab_job, "notebook": notebook_to_run}


def sync_hub_telemetry(hub_project: str, dry_run: bool = False) -> None:
    """Execute Step 2 telemetry synchronization stored procedures."""
    logger.info("STEP 2: HUB TELEMETRY SYNCHRONIZATION (%s)", hub_project)
    procs = ["sp_sync_curated_audit_events", "sp_sync_notebook_session_metrics", "sp_sync_ai_usage_metrics", "sp_aggregate_daily_compute_metrics", "sp_rollup_monthly_usage"]
    if dry_run:
        for p in procs:
            logger.info("  [DRY-RUN] Would execute CALL `%s.hub_telemetry.%s`()", hub_project, p)
        return
    bq_client = bigquery.Client(project=hub_project, location=REGION)
    for p in procs:
        logger.info("Calling `%s.hub_telemetry.%s`()...", hub_project, p)
        bq_client.query(f"CALL `{hub_project}.hub_telemetry.{p}`()").result()
        logger.info("  ✓ Completed %s", p)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaled Spoke Traffic & Activity Generator")
    parser.add_argument("--admin-prestep", action="store_true", help="Run Step 0 admin queries/uploads to exceed free tiers.")
    parser.add_argument("--current-user", action="store_true", help="Execute workload for the currently authenticated gcloud user.")
    parser.add_argument("--switch-accounts", action="store_true", help="Iteratively switch gcloud active account for each researcher.")
    parser.add_argument("--room", type=str, help="Filter execution to specific room_id.")
    parser.add_argument("--user", type=str, help="Filter execution to specific researcher email.")
    parser.add_argument("--sync-telemetry", action="store_true", help="Execute Step 2 BigQuery stored procedures.")
    parser.add_argument("--scale-factor", type=float, default=1.0, help="Activity scale multiplier.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without generating GCP cloud billing.")
    args = parser.parse_args()

    topo = load_topology()
    hub_project = topo.get("hub_project", {}).get("project_id", "gcp-rr-hub-core")
    initial_account = get_current_gcloud_account()

    if args.admin_prestep:
        run_admin_prestep(hub_project, dry_run=args.dry_run)

    if args.switch_accounts:
        logger.info("Iterating through all researchers with active gcloud account switching...")
        try:
            for room in topo.get("research_rooms", []):
                for res in room.get("researchers", []):
                    email = (res.get("primary_email") or res.get("email") or "").strip()
                    if not args.dry_run:
                        set_gcloud_account(email)
                    token = get_access_token() if not args.dry_run else "MOCK_TOKEN"
                    run_researcher_workload(room, res, token, scale_factor=args.scale_factor, dry_run=args.dry_run)
        finally:
            if initial_account and not args.dry_run:
                set_gcloud_account(initial_account)

    elif args.user:
        target_email = args.user.strip()
        match = find_room_for_researcher(topo, target_email)
        if not match:
            logger.error("User '%s' is not registered in fleet topology.", target_email)
            return 1
        room, res = match
        if not args.dry_run:
            set_gcloud_account(target_email)
        token = get_access_token() if not args.dry_run else "MOCK_TOKEN"
        run_researcher_workload(room, res, token, scale_factor=args.scale_factor, dry_run=args.dry_run)

    elif args.current_user or (not args.admin_prestep and not args.sync_telemetry and not args.room):
        match = find_room_for_researcher(topo, initial_account)
        if not match:
            logger.error("Current active account '%s' is not registered as a researcher in fleet topology. Specify --user <email> or run with --admin-prestep.", initial_account)
            return 1
        room, res = match
        token = get_access_token() if not args.dry_run else "MOCK_TOKEN"
        run_researcher_workload(room, res, token, scale_factor=args.scale_factor, dry_run=args.dry_run)

    elif args.room:
        for room in topo.get("research_rooms", []):
            if room["room_id"] == args.room:
                token = get_access_token() if not args.dry_run else "MOCK_TOKEN"
                for res in room.get("researchers", []):
                    run_researcher_workload(room, res, token, scale_factor=args.scale_factor, dry_run=args.dry_run)

    if args.sync_telemetry:
        sync_hub_telemetry(hub_project, dry_run=args.dry_run)

    logger.info("Scaled activity process cycle completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
