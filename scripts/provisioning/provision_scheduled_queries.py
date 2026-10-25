"""Provision and activate automated BigQuery Scheduled Queries in GCP Hub Core."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import bigquery_datatransfer_v1
from google.protobuf import field_mask_pb2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("provision_schedules")

PROJECT_ID = "gcp-rr-hub-core"
LOCATION = "me-west1"
DATASET_ID = "hub_telemetry"

SCHEDULE_CONFIGS: List[Dict[str, Any]] = [
    {
        "display_name": "rr-telemetry-15min-curation-sync",
        "schedule": "every 15 mins",
        "query": f"""
CALL `{PROJECT_ID}.{DATASET_ID}.sp_sync_curated_audit_events`();
CALL `{PROJECT_ID}.{DATASET_ID}.sp_sync_bigquery_queries`();
""".strip(),
    },
    {
        "display_name": "rr-telemetry-daily-finops-rollup",
        "schedule": "every 24 hours",
        "query": f"""
CALL `{PROJECT_ID}.{DATASET_ID}.sp_sync_storage_metrics`();
CALL `{PROJECT_ID}.{DATASET_ID}.sp_aggregate_daily_compute_metrics`();
CALL `{PROJECT_ID}.{DATASET_ID}.sp_rollup_monthly_usage`();
""".strip(),
    },
]


def get_client() -> bigquery_datatransfer_v1.DataTransferServiceClient:
    """Initialize BigQuery DataTransferServiceClient with regional endpoint."""
    client_options = {"api_endpoint": f"{LOCATION}-bigquerydatatransfer.googleapis.com"}
    return bigquery_datatransfer_v1.DataTransferServiceClient(client_options=client_options)


def list_existing_configs(
    client: bigquery_datatransfer_v1.DataTransferServiceClient, parent: str
) -> Dict[str, bigquery_datatransfer_v1.TransferConfig]:
    """List existing scheduled query configurations indexed by display name."""
    existing: Dict[str, bigquery_datatransfer_v1.TransferConfig] = {}
    try:
        for config in client.list_transfer_configs(parent=parent):
            if config.data_source_id == "scheduled_query":
                existing[config.display_name] = config
    except Exception as e:
        logger.warning("Error listing transfer configs: %s", e)
    return existing


def create_or_update_schedule(
    client: bigquery_datatransfer_v1.DataTransferServiceClient,
    parent: str,
    item: Dict[str, Any],
    existing_config: Optional[bigquery_datatransfer_v1.TransferConfig] = None,
) -> bigquery_datatransfer_v1.TransferConfig:
    """Create or update a scheduled query transfer configuration."""
    params = {"query": item["query"]}

    if existing_config:
        logger.info("Updating existing scheduled query: %s (%s)", item["display_name"], existing_config.name)
        existing_config.schedule = item["schedule"]
        existing_config.params = params
        existing_config.disabled = False
        update_mask = field_mask_pb2.FieldMask(paths=["schedule", "params", "disabled"])
        return client.update_transfer_config(
            transfer_config=existing_config, update_mask=update_mask
        )

    logger.info("Creating new scheduled query: %s", item["display_name"])
    transfer_config = bigquery_datatransfer_v1.TransferConfig(
        display_name=item["display_name"],
        data_source_id="scheduled_query",
        schedule=item["schedule"],
        params=params,
        disabled=False,
    )
    return client.create_transfer_config(parent=parent, transfer_config=transfer_config)


def trigger_and_verify_run(
    client: bigquery_datatransfer_v1.DataTransferServiceClient,
    config: bigquery_datatransfer_v1.TransferConfig,
    wait_seconds: int = 40,
) -> Dict[str, Any]:
    """Trigger a manual run of the transfer config and wait for its completion status."""
    logger.info("Triggering manual test run for: %s", config.display_name)
    now = datetime.now(timezone.utc)
    try:
        request = bigquery_datatransfer_v1.StartManualTransferRunsRequest(
            parent=config.name,
            requested_run_time=now,
        )
        response = client.start_manual_transfer_runs(request=request)
        runs = response.runs
        if not runs:
            logger.info("Manual run initiated without immediate run object returned.")
            return {"status": "TRIGGERED", "run_name": None}

        run_name = runs[0].name
        logger.info("Initiated run: %s (State: %s)", run_name, runs[0].state.name)

        start_time = time.time()
        while time.time() - start_time < wait_seconds:
            time.sleep(4)
            current_run = client.get_transfer_run(name=run_name)
            state_str = current_run.state.name
            logger.info("Run %s state: %s", run_name.split("/")[-1], state_str)
            if state_str in ("SUCCEEDED", "FAILED", "CANCELLED"):
                return {
                    "status": state_str,
                    "run_name": run_name,
                    "error_message": getattr(current_run.error_status, "message", None),
                }

        return {"status": "IN_PROGRESS", "run_name": run_name}
    except Exception as e:
        logger.error("Error triggering/verifying run for %s: %s", config.display_name, e)
        return {"status": "ERROR", "error_message": str(e)}


def main() -> int:
    """Main provisioning entry point."""
    logger.info("Starting provisioning of BigQuery Scheduled Queries in %s (Region: %s)...", PROJECT_ID, LOCATION)
    client = get_client()
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"

    existing_configs = list_existing_configs(client, parent)
    results = []

    for item in SCHEDULE_CONFIGS:
        existing = existing_configs.get(item["display_name"])
        try:
            config = create_or_update_schedule(client, parent, item, existing)
            run_result = trigger_and_verify_run(client, config, wait_seconds=45)
            results.append({
                "name": item["display_name"],
                "config_id": config.name.split("/")[-1],
                "resource_name": config.name,
                "schedule": config.schedule,
                "next_run_time": str(config.next_run_time) if config.next_run_time else "N/A",
                "run_status": run_result.get("status"),
                "error": run_result.get("error_message"),
            })
        except Exception as e:
            logger.error("Failed provisioning schedule %s: %s", item["display_name"], e)
            return 1

    logger.info("=" * 70)
    logger.info("SCHEDULED QUERY PROVISIONING SUMMARY")
    logger.info("=" * 70)
    for res in results:
        logger.info(
            "Schedule: %s | Config ID: %s | Cron: %s | Run Status: %s",
            res["name"], res["config_id"], res["schedule"], res["run_status"]
        )
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
