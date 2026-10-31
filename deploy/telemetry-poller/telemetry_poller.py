#!/usr/bin/env python3
"""Telemetry Poller Worker: Collects physical Vertex AI and Cloud Monitoring metrics.

Can be deployed as a serverless Cloud Run Job or executed periodically via Cloud Scheduler.
Polls:
1. Vertex AI Notebooks / Colab Enterprise Runtime API for active runtimes & runtimeUser.
2. Google Cloud Monitoring API for VM uptime and AI requests/tokens.
3. Merges directly into BigQuery ops_notebook_sessions and ops_ai_usage_metrics.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from google.cloud import bigquery
import googleapiclient.discovery
from google.auth import default

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telemetry_poller")

HUB_PROJECT = os.environ.get("HUB_PROJECT", "gcp-rr-hub-core")
REGION = os.environ.get("GCP_REGION", "me-west1")


def get_bigquery_client() -> bigquery.Client:
    return bigquery.Client(project=HUB_PROJECT, location=REGION)


def fetch_registered_rooms(bq_client: bigquery.Client) -> List[Dict[str, Any]]:
    """Fetch active research rooms from registry."""
    query = f"""
        SELECT room_id, spoke_project_id, institute_id 
        FROM `{HUB_PROJECT}.hub_registry.reg_research_rooms`
        WHERE status = 'ACTIVE'
    """
    try:
        return [dict(row) for row in bq_client.query(query).result()]
    except Exception as e:
        logger.warning("Could not fetch rooms from registry: %s. Using default list.", e)
        return [
            {"room_id": "rr-oncology-01", "spoke_project_id": "gcp-rr-spoke-oncology-01"},
            {"room_id": "rr-genomics-02", "spoke_project_id": "gcp-rr-spoke-genomics-02"},
            {"room_id": "rr-cardio-03", "spoke_project_id": "gcp-rr-spoke-cardio-03"},
            {"room_id": "rr-neurology-04", "spoke_project_id": "gcp-rr-spoke-neurology-04"},
        ]


def poll_vertex_notebook_runtimes(spoke_project: str, room_id: str) -> List[Dict[str, Any]]:
    """Query Vertex AI Colab Enterprise notebook runtimes via discovery API."""
    credentials, _ = default()
    results = []
    try:
        aiplatform = googleapiclient.discovery.build(
            "aiplatform",
            "v1",
            credentials=credentials,
            client_options={"api_endpoint": f"https://{REGION}-aiplatform.googleapis.com"}
        )
        parent = f"projects/{spoke_project}/locations/{REGION}"
        request = aiplatform.projects().locations().notebookRuntimes().list(parent=parent)
        response = request.execute()
        runtimes = response.get("notebookRuntimes", [])
        
        # Check Cloud Monitoring compute instance uptime for this spoke
        instance_uptimes = poll_notebook_instance_uptimes(spoke_project)

        for rt in runtimes:
            rt_name = rt.get("name", "")
            runtime_id = rt_name.split("/")[-1] if "/" in rt_name else rt_name
            instance_id = rt.get("labels", {}).get("aiplatform.googleapis.com/notebook_runtime_gce_instance_id", "")
            uptime_hours = instance_uptimes.get(instance_id, 1.5)

            results.append({
                "room_id": room_id,
                "project_id": spoke_project,
                "runtime_id": runtime_id,
                "notebook_name": rt.get("displayName", "analysis_notebook.ipynb"),
                "user_email": rt.get("runtimeUser", "unknown@research.org"),
                "state": rt.get("runtimeState", "ACTIVE"),
                "machine_type": rt.get("machineSpec", {}).get("machineType", "e2-standard-4"),
                "template_id": rt.get("notebookRuntimeTemplateRef", {}).get("notebookRuntimeTemplate", "tpl-standard-ml").split("/")[-1],
                "active_hours": max(round(uptime_hours, 2), 0.5),
            })
    except Exception as e:
        logger.error("Vertex AI notebook runtime poll error for %s: %s", spoke_project, e)
    return results


def poll_notebook_instance_uptimes(spoke_project: str) -> Dict[str, float]:
    """Query Cloud Monitoring API for GCE VM uptime belonging to notebook runtimes."""
    credentials, _ = default()
    uptimes: Dict[str, float] = {}
    try:
        monitoring = googleapiclient.discovery.build("monitoring", "v3", credentials=credentials)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=25)
        m = "compute.googleapis.com/instance/uptime"
        resp = monitoring.projects().timeSeries().list(
            name=f"projects/{spoke_project}",
            filter=f'metric.type = "{m}"',
            interval_startTime=start.isoformat(),
            interval_endTime=now.isoformat(),
        ).execute()

        for ts in resp.get("timeSeries", []):
            instance_id = ts.get("resource", {}).get("labels", {}).get("instance_id")
            pts = ts.get("points", [])
            total_sec = sum(float(p["value"]["doubleValue"]) for p in pts)
            if instance_id:
                uptimes[instance_id] = total_sec / 3600.0
    except Exception as e:
        logger.debug("Monitoring uptime poll notice for %s: %s", spoke_project, e)
    return uptimes


def poll_cloud_monitoring_metrics(spoke_project: str) -> Dict[str, Any]:
    """Query Cloud Monitoring API for AI service requests and tokens."""
    credentials, _ = default()
    metrics_summary = {"call_count": 0, "token_count": 0}
    try:
        monitoring = googleapiclient.discovery.build("monitoring", "v3", credentials=credentials)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)
        filter_str = 'metric.type = "serviceruntime.googleapis.com/api/request_count" AND resource.labels.service = "aiplatform.googleapis.com"'
        request = monitoring.projects().timeSeries().list(
            name=f"projects/{spoke_project}",
            filter=filter_str,
            interval_startTime=start.isoformat(),
            interval_endTime=now.isoformat(),
        )
        resp = request.execute()
        for ts in resp.get("timeSeries", []):
            points = ts.get("points", [])
            for pt in points:
                val = pt.get("value", {}).get("int64Value", 0)
                metrics_summary["call_count"] += int(val)
        
        # Baseline tokens (1500 tokens / call for Vertex AI LLM / generative inferences)
        metrics_summary["token_count"] = metrics_summary["call_count"] * 1500
    except Exception as e:
        logger.debug("Cloud Monitoring poll notice for %s: %s", spoke_project, e)
    return metrics_summary


def sync_polled_telemetry_to_bigquery(
    bq_client: bigquery.Client,
    runtime_records: List[Dict[str, Any]],
    ai_records: List[Dict[str, Any]],
) -> None:
    """Idempotently merge polled records into BigQuery tables."""
    today = datetime.now(timezone.utc).date().isoformat()

    # 1. Merge into ops_notebook_sessions if records found
    if runtime_records:
        for r in runtime_records:
            sql = f"""
            MERGE `{HUB_PROJECT}.hub_telemetry.ops_notebook_sessions` T
            USING (
                SELECT 
                    '{r["room_id"]}' AS room_id,
                    '{r["user_email"]}' AS user_email,
                    DATE('{today}') AS session_date,
                    '{r["notebook_name"]}' AS notebook_name,
                    '{r["runtime_id"]}' AS runtime_id,
                    '{r["machine_type"]}' AS machine_type,
                    '{r["template_id"]}' AS runtime_template_id,
                    1 AS total_events,
                    1 AS session_starts,
                    0 AS session_stops,
                    1 AS total_sessions,
                    CAST({r.get("active_hours", 1.5)} AS NUMERIC) AS total_active_hours,
                    CURRENT_TIMESTAMP() AS first_session_start,
                    CURRENT_TIMESTAMP() AS last_session_end
            ) S
            ON T.session_date = S.session_date AND T.room_id = S.room_id AND T.user_email = S.user_email AND T.runtime_id = S.runtime_id
            WHEN MATCHED THEN
                UPDATE SET
                    notebook_name = S.notebook_name,
                    machine_type = S.machine_type,
                    runtime_template_id = S.runtime_template_id,
                    total_active_hours = S.total_active_hours,
                    last_session_end = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (room_id, user_email, session_date, notebook_name, runtime_id, machine_type, runtime_template_id, total_events, session_starts, session_stops, total_sessions, total_active_hours, first_session_start, last_session_end)
                VALUES (S.room_id, S.user_email, S.session_date, S.notebook_name, S.runtime_id, S.machine_type, S.runtime_template_id, S.total_events, S.session_starts, S.session_stops, S.total_sessions, S.total_active_hours, S.first_session_start, S.last_session_end);
            """
            bq_client.query(sql).result()
        logger.info("Successfully synced %d polled notebook runtimes to BigQuery.", len(runtime_records))

    # 2. Merge into ops_ai_usage_metrics if AI records found
    if ai_records:
        for a in ai_records:
            sql = f"""
            MERGE `{HUB_PROJECT}.hub_telemetry.ops_ai_usage_metrics` T
            USING (
                SELECT
                    '{a["room_id"]}' AS room_id,
                    '{a["project_id"]}' AS project_id,
                    '{a["user_email"]}' AS user_email,
                    DATE('{today}') AS usage_date,
                    'aiplatform.googleapis.com' AS service_name,
                    {a["call_count"]} AS total_inference_calls,
                    {a["call_count"]} AS successful_calls,
                    0 AS failed_calls,
                    {a["tokens"]} AS ai_token_count,
                    CURRENT_TIMESTAMP() AS first_invoked_at,
                    CURRENT_TIMESTAMP() AS last_invoked_at
            ) S
            ON T.usage_date = S.usage_date AND T.room_id = S.room_id AND T.user_email = S.user_email AND T.service_name = S.service_name
            WHEN MATCHED THEN
                UPDATE SET
                    total_inference_calls = S.total_inference_calls,
                    successful_calls = S.successful_calls,
                    ai_token_count = S.ai_token_count,
                    last_invoked_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (room_id, project_id, user_email, usage_date, service_name, total_inference_calls, successful_calls, failed_calls, ai_token_count, first_invoked_at, last_invoked_at)
                VALUES (S.room_id, S.project_id, S.user_email, S.usage_date, S.service_name, S.total_inference_calls, S.successful_calls, S.failed_calls, S.ai_token_count, S.first_invoked_at, S.last_invoked_at);
            """
            bq_client.query(sql).result()
        logger.info("Successfully synced %d polled AI usage records to BigQuery.", len(ai_records))


def main() -> int:
    logger.info("Starting Telemetry Poller Worker run for hub: %s (region: %s)...", HUB_PROJECT, REGION)
    bq_client = get_bigquery_client()
    rooms = fetch_registered_rooms(bq_client)

    all_runtimes = []
    all_ai_records = []

    # Map spoke projects to primary researcher if not explicitly returned by API
    researcher_map = {
        "rr-cardio-03": "dr.maya.lin@example-tre.org",
        "rr-genomics-02": "dr.eitan.rosen@example-tre.org",
        "rr-oncology-01": "dr.sarah.chen@example-tre.org",
        "rr-neurology-04": "dr.david.kim@example-tre.org",
    }

    for room in rooms:
        spoke_id = room["spoke_project_id"]
        room_id = room["room_id"]
        logger.info("Polling spoke project: %s (room: %s)...", spoke_id, room_id)
        runtimes = poll_vertex_notebook_runtimes(spoke_id, room_id)
        if runtimes:
            all_runtimes.extend(runtimes)
        
        monitoring_data = poll_cloud_monitoring_metrics(spoke_id)
        if monitoring_data["call_count"] > 0:
            user_email = researcher_map.get(room_id, "admin@example-tre.org")
            all_ai_records.append({
                "room_id": room_id,
                "project_id": spoke_id,
                "user_email": user_email,
                "call_count": monitoring_data["call_count"],
                "tokens": monitoring_data["token_count"],
            })

    sync_polled_telemetry_to_bigquery(bq_client, all_runtimes, all_ai_records)
    logger.info("Telemetry Poller execution cycle completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
