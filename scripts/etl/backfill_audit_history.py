#!/usr/bin/env python3
"""Idempotent historical Cloud Audit Log backfill into BigQuery hub_telemetry.ops_audit_events_curated."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import uuid
from datetime import datetime
from google.cloud import bigquery
from googleapiclient.discovery import build
import google.auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_audit")

HUB_PROJECT = "gcp-rr-hub-core"
REGION = "me-west1"
START_TIME = "2026-09-26T00:00:00Z"


def resolve_category(service_name: str, method_name: str, resource_name: str) -> str:
    s = (service_name or "").lower()
    m = (method_name or "").lower()
    r = (resource_name or "").lower()
    if any(k in s for k in ["aiplatform"]) or any(k in m for k in ["predict", "generatecontent", "counttokens"]):
        return "AI_INFERENCE"
    if any(k in s for k in ["notebooks", "compute"]) or any(k in m for k in ["instance", "session"]):
        return "COMPUTE_SESSION"
    if any(k in s for k in ["iam", "resourcemanager"]) or any(k in m for k in ["iampolicy", "key"]):
        return "IAM_SECURITY"
    if "storage" in s and ("export" in r or "export" in m or "copy" in m):
        return "STORAGE_EGRESS"
    if "bigquery" in s or "storage" in s:
        return "DATA_ACCESS"
    return "DATA_ACCESS"


def resolve_description(service_name: str, method_name: str, resource_name: str, principal: str) -> str:
    s = (service_name or "").lower()
    m = (method_name or "").lower()
    r = (resource_name or "").lower()
    p = principal or "user"
    res = resource_name or "resource"

    if "bigquery" in s and "job" in m:
        return f"BigQuery job executed by {p} on {resource_name or 'BigQuery resource'}"
    if "storage" in s and ("export" in r or "copy" in m):
        return f"Egress storage transfer initiated by {p} to {resource_name or 'export bucket'}"
    if "storage" in s:
        return f"Cloud Storage access by {p} on {resource_name or 'storage object'}"
    if "notebooks" in s or "instance" in m:
        return f"Compute session operation ({method_name}) by {p}"
    if "aiplatform" in s or "generatecontent" in m:
        return f"AI inference invocation by {p}"
    if "iam" in s or "iampolicy" in m:
        return f"IAM authorization change by {p} on {res}"
    return f"{method_name or 'Action'} performed on {res} by {p}"


def fetch_audit_logs_for_project(logging_service, project_id: str, room_id: str):
    logger.info("Fetching audit logs for %s (%s)...", project_id, room_id)
    filter_str = f'logName:"cloudaudit.googleapis.com" AND timestamp >= "{START_TIME}"'
    page_token = None
    records = []

    while True:
        body = {
            "resourceNames": [f"projects/{project_id}"],
            "filter": filter_str,
            "pageSize": 1000,
        }
        if page_token:
            body["pageToken"] = page_token
        res = logging_service.entries().list(body=body).execute()
        entries = res.get("entries", [])
        for e in entries:
            proto = e.get("protoPayload", {})
            auth_info = proto.get("authenticationInfo", {})
            status_obj = proto.get("status", {})

            service_name = proto.get("serviceName") or "cloudaudit.googleapis.com"
            method_name = proto.get("methodName") or "UnknownAction"
            resource_name = proto.get("resourceName") or e.get("resource", {}).get("labels", {}).get("project_id")
            principal = auth_info.get("principalEmail") or "system@google.com"

            status_code = status_obj.get("code")
            if status_code is None or status_code == 0:
                status = "SUCCESS"
            else:
                status = status_obj.get("message") or "ERROR"

            severity = e.get("severity") or "INFO"
            log_id = e.get("insertId") or str(uuid.uuid4())
            ts = e.get("timestamp")

            cat = resolve_category(service_name, method_name, resource_name)
            desc = resolve_description(service_name, method_name, resource_name, principal)

            meta = proto.get("metadataJson") or proto.get("serviceData") or proto.get("request")
            meta_str = json.dumps(meta) if isinstance(meta, (dict, list)) else (str(meta) if meta else None)

            records.append({
                "log_id": log_id,
                "timestamp": ts,
                "room_id": room_id,
                "project_id": project_id,
                "principal_email": principal,
                "category": cat,
                "service_name": service_name,
                "action_name": method_name,
                "resource_name": resource_name,
                "status": status,
                "severity": severity,
                "description": desc,
                "metadata_json": meta_str,
            })

        page_token = res.get("nextPageToken")
        if not page_token:
            break

    logger.info("Found %d audit logs for %s (%s)", len(records), project_id, room_id)
    return records


def main():
    credentials, _ = google.auth.default()
    bq_client = bigquery.Client(project=HUB_PROJECT, location=REGION, credentials=credentials)
    logging_service = build("logging", "v2", credentials=credentials)

    # 1. Dynamically retrieve room mappings
    rooms_query = f"SELECT room_id, spoke_project_id FROM `{HUB_PROJECT}.hub_registry.reg_research_rooms`"
    rooms_df = list(bq_client.query(rooms_query).result())
    target_projects = [(HUB_PROJECT, "hub-core")]
    for r in rooms_df:
        target_projects.append((r["spoke_project_id"], r["room_id"]))

    logger.info("Target projects for backfill: %s", target_projects)

    # 2. Extract and transform all logs
    all_records = []
    stats_per_room = {}
    for proj_id, room_id in target_projects:
        records = fetch_audit_logs_for_project(logging_service, proj_id, room_id)
        all_records.extend(records)
        stats_per_room[room_id] = len(records)

    logger.info("Total audit records extracted: %d across %d projects", len(all_records), len(target_projects))

    # 3. Load into staging table and idempotent MERGE
    staging_table_id = f"{HUB_PROJECT}.hub_telemetry._backfill_audit_staging"
    schema = [
        bigquery.SchemaField("log_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("room_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("project_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("principal_email", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("service_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("action_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("resource_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("metadata_json", "STRING", mode="NULLABLE"),
    ]

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    logger.info("Loading %d rows into staging table %s...", len(all_records), staging_table_id)
    # Deduplicate in-memory by log_id before staging load
    deduped_records = {}
    for r in all_records:
        deduped_records[r["log_id"]] = r
    unique_records = list(deduped_records.values())
    logger.info("Unique records after in-memory deduplication: %d", len(unique_records))

    load_job = bq_client.load_table_from_json(unique_records, staging_table_id, job_config=job_config)
    load_job.result()
    logger.info("Staging load complete.")

    # 4. Perform idempotent MERGE into curated table
    merge_query = f"""
    MERGE `{HUB_PROJECT}.hub_telemetry.ops_audit_events_curated` T
    USING `{staging_table_id}` S
    ON T.log_id = S.log_id
    WHEN NOT MATCHED THEN
        INSERT (log_id, timestamp, room_id, project_id, principal_email, category, service_name, action_name, resource_name, status, severity, description, metadata_json)
        VALUES (S.log_id, S.timestamp, S.room_id, S.project_id, S.principal_email, S.category, S.service_name, S.action_name, S.resource_name, S.status, S.severity, S.description, S.metadata_json)
    """
    logger.info("Executing idempotent MERGE into ops_audit_events_curated...")
    bq_client.query(merge_query).result()
    logger.info("MERGE complete.")

    # 5. Clean up staging table
    bq_client.delete_table(staging_table_id, not_found_ok=True)
    logger.info("Staging table cleaned up.")

    # Print summary statistics
    print("\n" + "="*60)
    print("BACKFILL AUDIT HISTORY SUMMARY:")
    for room, cnt in stats_per_room.items():
        print(f"  * {room}: {cnt} logs extracted")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
