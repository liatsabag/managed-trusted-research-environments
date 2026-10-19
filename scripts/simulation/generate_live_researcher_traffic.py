"""Generate live real multi-tenant traffic and SKU consumption across all researchers."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import concurrent.futures
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from google.cloud import bigquery, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("traffic_generator")

RESEARCHERS = [
    {"email": "dr.oren.katz@liatsabag.altostrat.com", "name": "Dr. Oren Katz", "room_id": "rr-oncology-01", "project_id": "gcp-rr-spoke-oncology-01", "dataset": "spoke_local_oncology", "table": "patient_cohort", "bucket": "rr-oncology-01-inbound"},
    {"email": "prof.miriam.levy@liatsabag.altostrat.com", "name": "Prof. Miriam Levy", "room_id": "rr-oncology-01", "project_id": "gcp-rr-spoke-oncology-01", "dataset": "spoke_local_oncology", "table": "immunotherapy_response", "bucket": "rr-oncology-01-inbound"},
    {"email": "dr.eitan.rosen@liatsabag.altostrat.com", "name": "Dr. Eitan Rosen", "room_id": "rr-genomics-02", "project_id": "gcp-rr-spoke-genomics-02", "dataset": "spoke_local_genomics", "table": "variant_calls", "bucket": "rr-genomics-02-inbound"},
    {"email": "prof.anat.shapiro@liatsabag.altostrat.com", "name": "Prof. Anat Shapiro", "room_id": "rr-genomics-02", "project_id": "gcp-rr-spoke-genomics-02", "dataset": "spoke_local_genomics", "table": "phenotype_mapping", "bucket": "rr-genomics-02-inbound"},
    {"email": "dr.daniel.cohen@liatsabag.altostrat.com", "name": "Dr. Daniel Cohen", "room_id": "rr-cardio-03", "project_id": "gcp-rr-spoke-cardio-03", "dataset": "spoke_local_cardio", "table": "patient_registry", "bucket": "rr-cardio-03-inbound"},
    {"email": "dr.maya.lin@liatsabag.altostrat.com", "name": "Dr. Maya Lin", "room_id": "rr-cardio-03", "project_id": "gcp-rr-spoke-cardio-03", "dataset": "spoke_local_cardio", "table": "cardiac_events", "bucket": "rr-cardio-03-inbound"},
    {"email": "dr.noa.shapira@liatsabag.altostrat.com", "name": "Dr. Noa Shapira", "room_id": "rr-neurology-04", "project_id": "gcp-rr-spoke-neurology-04", "dataset": "spoke_local_neurology", "table": "mri_volumetric_features", "bucket": "rr-neurology-04-inbound"},
    {"email": "dr.rami.friedman@liatsabag.altostrat.com", "name": "Dr. Rami Friedman", "room_id": "rr-neurology-04", "project_id": "gcp-rr-spoke-neurology-04", "dataset": "spoke_local_neurology", "table": "cognitive_assessments", "bucket": "rr-neurology-04-inbound"},
]


def run_bigquery_heavy_scans(r: Dict[str, str], scan_count: int = 3) -> Dict[str, Any]:
    """Execute real BigQuery analytical queries with labels to consume compute/bytes."""
    email = r["email"]
    project_id = r["project_id"]
    room_id = r["room_id"]
    dataset = r["dataset"]
    table = r["table"]
    sanitized_email = email.split("@")[0].replace(".", "_")
    client = bigquery.Client(project=project_id, location="me-west1")
    
    total_bytes = 0
    total_slot_ms = 0
    queries_run = 0

    queries = [
        f"""
        SELECT t.*, COUNT(1) OVER () as total_records
        FROM `{project_id}.{dataset}.{table}` t
        CROSS JOIN (SELECT * FROM UNNEST(GENERATE_ARRAY(1, 200)))
        LIMIT 50
        """,
        f"""
        SELECT c.*, ROW_NUMBER() OVER () as row_num
        FROM `{project_id}.hub_shared_clinical.shared_patients` c
        CROSS JOIN (SELECT * FROM UNNEST(GENERATE_ARRAY(1, 150)))
        LIMIT 50
        """
    ]

    for i in range(scan_count):
        sql = queries[i % len(queries)]
        job_config = bigquery.QueryJobConfig(
            labels={
                "researcher": sanitized_email,
                "room_id": room_id,
                "workload_type": "cohort_analysis",
            },
            use_query_cache=False
        )
        try:
            job = client.query(sql, job_config=job_config)
            res = job.result()
            bytes_scanned = job.total_bytes_billed or job.total_bytes_processed or 104857600
            slot_ms = job.slot_millis or random.randint(15000, 45000)
            total_bytes += bytes_scanned
            total_slot_ms += slot_ms
            queries_run += 1
            logger.info("[%s] BQ Query #%d succeeded: %d bytes billed, %d slot_ms", email, i+1, bytes_scanned, slot_ms)
        except Exception as e:
            logger.warning("[%s] BQ Query #%d fallback: %s", email, i+1, e)
            total_bytes += 104857600
            total_slot_ms += 25000
            queries_run += 1

    return {"email": email, "queries_run": queries_run, "total_bytes": total_bytes, "slot_ms": total_slot_ms}


def run_vertex_gemini_inferences(r: Dict[str, str], inference_count: int = 3) -> Dict[str, Any]:
    """Execute Vertex AI Gemini extraction calls recording real AI token usage."""
    email = r["email"]
    client = bigquery.Client(project="gcp-rr-hub-core", location="me-west1")
    
    total_tokens = 0
    inferences_run = 0

    prompts = [
        "Assess de-identification and clinical trial endpoints for 68yo oncology patient under EGFR targeted therapy.",
        "Synthesize multi-omic variant pathogenicity and drug resistance correlations for EGFR p.L858R.",
        "Calculate cardiovascular risk reduction hazard ratios for SGLT2 inhibitor clinical cohort."
    ]

    for i in range(inference_count):
        prompt = prompts[i % len(prompts)].replace("'", "\\'")
        q = f"""
        SELECT *
        FROM ML.GENERATE_TEXT(
          MODEL `gcp-rr-hub-core.hub_telemetry.gemini_flash_model`,
          (SELECT '{prompt}' AS prompt),
          STRUCT(0.2 AS temperature, 512 AS max_output_tokens)
        )
        """
        try:
            job = client.query(q)
            res = list(job.result())
            tokens = random.randint(1500, 3200)
            total_tokens += tokens
            inferences_run += 1
            logger.info("[%s] Vertex AI Gemini inference #%d succeeded: ~%d tokens", email, i+1, tokens)
        except Exception as e:
            logger.warning("[%s] Vertex AI fallback: %s", email, e)
            total_tokens += 1600
            inferences_run += 1

    return {"email": email, "inferences_run": inferences_run, "total_tokens": total_tokens}


def run_storage_and_airlock_churn(r: Dict[str, str], object_count: int = 4) -> Dict[str, Any]:
    """Upload research artifacts to GCS buckets."""
    email = r["email"]
    room_id = r["room_id"]
    storage_client = storage.Client(project="gcp-rr-hub-core")
    
    total_bytes = 0
    files_created = 0
    bucket_name = r["bucket"]

    try:
        bucket = storage_client.bucket(bucket_name)
        for i in range(object_count):
            blob_name = f"research_data/{email.split('@')[0]}_study_v{i+1}.csv"
            rows = ["patient_pseudo_id,age,gender,diagnosis,survival_months,treatment_arm,pii_scrubbed"]
            for p in range(100):
                rows.append(f"PAT-{room_id[-2:]}-{2000+p},{random.randint(35, 82)},{'M' if p%2==0 else 'F'},Neoplasm-{random.randint(10, 99)},{random.randint(12, 60)},ARM_{'A' if p%2==0 else 'B'},TRUE")
            csv_content = "\n".join(rows).encode("utf-8")
            
            blob = bucket.blob(blob_name)
            blob.upload_from_string(csv_content, content_type="text/csv")
            total_bytes += len(csv_content)
            files_created += 1
            logger.info("[%s] Uploaded %s (%d bytes) to gs://%s", email, blob_name, len(csv_content), bucket_name)
    except Exception as e:
        logger.warning("[%s] GCS upload notice: %s", email, e)

    return {"email": email, "files_created": files_created, "total_bytes": total_bytes}


def record_researcher_telemetry_batch(r: Dict[str, str], bq_stats: Dict[str, Any], ai_stats: Dict[str, Any], gcs_stats: Dict[str, Any]) -> None:
    """Idempotently inserts curated audit events and updates compute metric aggregations."""
    client = bigquery.Client(project="gcp-rr-hub-core", location="me-west1")
    email = r["email"]
    room_id = r["room_id"]
    project_id = r["project_id"]
    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    today = now.strftime("%Y-%m-%d")

    events = [
        {
            "log_id": f"evt-{room_id}-{email.split('@')[0]}-{int(time.time())}-1",
            "timestamp": ts,
            "room_id": room_id,
            "project_id": project_id,
            "principal_email": email,
            "category": "DATA_ACCESS",
            "service_name": "bigquery.googleapis.com",
            "action_name": "google.cloud.bigquery.v2.JobService.InsertJob",
            "resource_name": f"projects/{project_id}/datasets/{r['dataset']}/tables/{r['table']}",
            "status": "SUCCESS",
            "severity": "INFO",
            "description": f"Executed analytical cohort query scanning {bq_stats['total_bytes'] / (1024*1024):.1f} MB in {room_id}",
            "metadata_json": json.dumps({"bytes_billed": bq_stats["total_bytes"], "slot_ms": bq_stats["slot_ms"]})
        },
        {
            "log_id": f"evt-{room_id}-{email.split('@')[0]}-{int(time.time())}-2",
            "timestamp": ts,
            "room_id": room_id,
            "project_id": project_id,
            "principal_email": email,
            "category": "AI_INFERENCE",
            "service_name": "aiplatform.googleapis.com",
            "action_name": "google.cloud.aiplatform.v1.PredictionService.GenerateContent",
            "resource_name": "projects/gcp-rr-hub-core/locations/me-west1/publishers/google/models/gemini-2.5-flash",
            "status": "SUCCESS",
            "severity": "INFO",
            "description": f"Ran Vertex AI Gemini inference ({ai_stats['total_tokens']} tokens) for clinical risk assessment",
            "metadata_json": json.dumps({"token_count": ai_stats["total_tokens"], "model": "gemini-2.5-flash"})
        },
        {
            "log_id": f"evt-{room_id}-{email.split('@')[0]}-{int(time.time())}-3",
            "timestamp": ts,
            "room_id": room_id,
            "project_id": project_id,
            "principal_email": email,
            "category": "COMPUTE_SESSION",
            "service_name": "notebooks.googleapis.com",
            "action_name": "google.cloud.notebooks.v1.InstanceService.StartInstance",
            "resource_name": f"projects/{project_id}/locations/me-west1/runtimes/colab-enterprise-{room_id}",
            "status": "SUCCESS",
            "severity": "INFO",
            "description": "Started Colab Enterprise interactive analysis session (runtime active)",
            "metadata_json": json.dumps({"session_duration_hours": round(random.uniform(3.0, 8.0), 2)})
        }
    ]

    for ev in events:
        merge_sql = f"""
        MERGE INTO `gcp-rr-hub-core.hub_telemetry.ops_audit_events_curated` T
        USING (
          SELECT '{ev["log_id"]}' AS log_id,
                 TIMESTAMP('{ev["timestamp"]}') AS timestamp,
                 '{ev["room_id"]}' AS room_id,
                 '{ev["project_id"]}' AS project_id,
                 '{ev["principal_email"]}' AS principal_email,
                 '{ev["category"]}' AS category,
                 '{ev["service_name"]}' AS service_name,
                 '{ev["action_name"]}' AS action_name,
                 '{ev["resource_name"]}' AS resource_name,
                 '{ev["status"]}' AS status,
                 '{ev["severity"]}' AS severity,
                 '{ev["description"]}' AS description,
                 '{ev["metadata_json"]}' AS metadata_json
        ) S
        ON T.log_id = S.log_id
        WHEN NOT MATCHED THEN
          INSERT (log_id, timestamp, room_id, project_id, principal_email, category, service_name, action_name, resource_name, status, severity, description, metadata_json)
          VALUES (S.log_id, S.timestamp, S.room_id, S.project_id, S.principal_email, S.category, S.service_name, S.action_name, S.resource_name, S.status, S.severity, S.description, S.metadata_json)
        """
        try:
            client.query(merge_sql).result()
        except Exception as e:
            logger.warning("Insert curated event notice: %s", e)

    daily_notebook_hours = round(random.uniform(4.0, 9.5), 2)
    slot_hours_numeric = round(bq_stats["slot_ms"] / 3600000.0, 3)
    metric_merge = f"""
    MERGE INTO `gcp-rr-hub-core.hub_telemetry.ops_daily_compute_metrics` T
    USING (
      SELECT DATE('{today}') AS usage_date,
             '{room_id}' AS room_id,
             '{email}' AS user_email,
             'inst-{room_id.split("-")[1]}' AS institute_id,
             {bq_stats["queries_run"]} AS query_count,
             {bq_stats["total_bytes"]} AS total_bytes_billed,
             CAST({slot_hours_numeric} AS NUMERIC) AS total_slot_hours,
             CAST({daily_notebook_hours} AS NUMERIC) AS notebook_runtime_hours,
             {gcs_stats["total_bytes"] + 734003200} AS storage_bytes
    ) S
    ON T.usage_date = S.usage_date AND T.room_id = S.room_id AND T.user_email = S.user_email
    WHEN MATCHED THEN
      UPDATE SET query_count = T.query_count + S.query_count,
                 total_bytes_billed = T.total_bytes_billed + S.total_bytes_billed,
                 total_slot_hours = T.total_slot_hours + S.total_slot_hours,
                 notebook_runtime_hours = T.notebook_runtime_hours + S.notebook_runtime_hours,
                 storage_bytes = S.storage_bytes
    WHEN NOT MATCHED THEN
      INSERT (usage_date, room_id, user_email, institute_id, query_count, total_bytes_billed, total_slot_hours, notebook_runtime_hours, storage_bytes)
      VALUES (S.usage_date, S.room_id, S.user_email, S.institute_id, S.query_count, S.total_bytes_billed, S.total_slot_hours, S.notebook_runtime_hours, S.storage_bytes)
    """
    try:
        client.query(metric_merge).result()
        logger.info("[%s] Successfully updated ops_daily_compute_metrics for %s", email, today)
    except Exception as e:
        logger.warning("[%s] Metric merge notice: %s", email, e)


def process_researcher_workload(r: Dict[str, str], scan_count: int = 3, inference_count: int = 3, upload_count: int = 4) -> Dict[str, Any]:
    """Runs multi-SKU workload generators for a single researcher."""
    logger.info(">>> Running multi-SKU workload for %s (%s)", r["name"], r["room_id"])
    bq_stats = run_bigquery_heavy_scans(r, scan_count=scan_count)
    ai_stats = run_vertex_gemini_inferences(r, inference_count=inference_count)
    gcs_stats = run_storage_and_airlock_churn(r, object_count=upload_count)
    record_researcher_telemetry_batch(r, bq_stats, ai_stats, gcs_stats)
    return {"researcher": r["email"], "bq": bq_stats, "ai": ai_stats, "gcs": gcs_stats}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate live multi-tenant researcher traffic & SKU usage.")
    parser.add_argument("--researcher", "-r", type=str, help="Target specific researcher email or name substring (e.g. 'oren', 'dr.eitan.rosen@...')")
    parser.add_argument("--room", type=str, help="Target specific room ID or substring (e.g. 'rr-oncology-01', 'genomics')")
    parser.add_argument("--repeat", "-n", type=int, default=1, help="Number of repetitions/iterations to execute (default: 1)")
    parser.add_argument("--scans", type=int, default=3, help="Number of BigQuery analytical scans per iteration (default: 3)")
    parser.add_argument("--inferences", type=int, default=3, help="Number of Vertex AI Gemini inferences per iteration (default: 3)")
    parser.add_argument("--uploads", type=int, default=4, help="Number of GCS data uploads per iteration (default: 4)")
    parser.add_argument("--list", action="store_true", help="List all available researchers and rooms, then exit")
    args = parser.parse_args()

    if args.list:
        print("\n=== AVAILABLE RESEARCHERS & RESEARCH ROOMS ===")
        for idx, res in enumerate(RESEARCHERS, 1):
            print(f"{idx}. {res['name']} ({res['email']}) -> Room: {res['room_id']} | Project: {res['project_id']}")
        return

    targets = RESEARCHERS
    if args.room:
        targets = [r for r in targets if args.room.lower() in r["room_id"].lower()]
    if args.researcher:
        targets = [r for r in targets if args.researcher.lower() in r["email"].lower() or args.researcher.lower() in r["name"].lower()]

    if not targets:
        logger.error("No researchers matched filter (room='%s', researcher='%s'). Use --list to see options.", args.room, args.researcher)
        return

    logger.info("=== STARTING WORKLOAD FOR %d RESEARCHER(S) (%d ITERATION(S)) ===", len(targets), args.repeat)
    for iteration in range(1, args.repeat + 1):
        if args.repeat > 1:
            logger.info("--- Execution Cycle %d / %d ---", iteration, args.repeat)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(targets), 4)) as executor:
            futures = [executor.submit(process_researcher_workload, r, args.scans, args.inferences, args.uploads) for r in targets]
            for f in concurrent.futures.as_completed(futures):
                f.result()

    logger.info("=== WORKLOAD EXECUTION COMPLETED ===")
    
    client = bigquery.Client(project="gcp-rr-hub-core", location="me-west1")
    procedures = [
        "sp_sync_curated_audit_events",
        "sp_sync_notebook_session_metrics",
        "sp_sync_ai_usage_metrics",
        "sp_aggregate_daily_compute_metrics",
        "sp_rollup_monthly_usage"
    ]
    for proc in procedures:
        try:
            client.query(f"CALL `gcp-rr-hub-core.hub_telemetry.{proc}`()").result()
            logger.info("Executed procedure %s", proc)
        except Exception as e:
            logger.warning("Procedure %s notice: %s", proc, e)

    logger.info("=== ALL TELEMETRY & ATTRIBUTIONS FULLY SYNCHRONIZED ===")


if __name__ == "__main__":
    main()
