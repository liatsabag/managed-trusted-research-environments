#!/usr/bin/env python3
"""Sync and verify BigQuery telemetry DDLs, schemas, and stored procedures."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import logging
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_telemetry")

HUB_PROJECT = "gcp-rr-hub-core"
REGION = "me-west1"


def main():
    client = bigquery.Client(project=HUB_PROJECT, location=REGION)

    # 1. Update ops_daily_compute_metrics table schema if columns missing
    table_ref = client.get_table(f"{HUB_PROJECT}.hub_telemetry.ops_daily_compute_metrics")
    existing_cols = {field.name for field in table_ref.schema}
    logger.info("Existing columns in ops_daily_compute_metrics: %s", existing_cols)

    new_schema = list(table_ref.schema)
    if "ai_inference_count" not in existing_cols:
        new_schema.append(bigquery.SchemaField("ai_inference_count", "INT64", mode="NULLABLE"))
    if "ai_token_count" not in existing_cols:
        new_schema.append(bigquery.SchemaField("ai_token_count", "INT64", mode="NULLABLE"))

    if len(new_schema) > len(table_ref.schema):
        table_ref.schema = new_schema
        client.update_table(table_ref, ["schema"])
        logger.info("Updated ops_daily_compute_metrics schema with AI metric columns.")

    # 2. Update ops_notebook_sessions table schema for Colab Enterprise tracking
    try:
        nb_table_ref = client.get_table(f"{HUB_PROJECT}.hub_telemetry.ops_notebook_sessions")
        nb_cols = {field.name for field in nb_table_ref.schema}
        logger.info("Existing columns in ops_notebook_sessions: %s", nb_cols)

        nb_new_schema = list(nb_table_ref.schema)
        if "notebook_name" not in nb_cols:
            nb_new_schema.append(bigquery.SchemaField("notebook_name", "STRING", mode="NULLABLE"))
        if "runtime_id" not in nb_cols:
            nb_new_schema.append(bigquery.SchemaField("runtime_id", "STRING", mode="NULLABLE"))
        if "machine_type" not in nb_cols:
            nb_new_schema.append(bigquery.SchemaField("machine_type", "STRING", mode="NULLABLE"))
        if "runtime_template_id" not in nb_cols:
            nb_new_schema.append(bigquery.SchemaField("runtime_template_id", "STRING", mode="NULLABLE"))

        if len(nb_new_schema) > len(nb_table_ref.schema):
            nb_table_ref.schema = nb_new_schema
            client.update_table(nb_table_ref, ["schema"])
            logger.info("Updated ops_notebook_sessions schema with Colab Enterprise metadata columns.")
    except Exception as e:
        logger.warning("ops_notebook_sessions check/update notice: %s", e)

    # 3. Execute SQL files to update procedures and views
    sql_files = [
        "scripts/sql/view_billing_export.sql",
        "scripts/sql/curate_audit_events.sql",
        "scripts/sql/finops_usage_tracking.sql",
        "scripts/sql/aggregate_compute_metrics.sql",
    ]
    for sf in sql_files:
        with open(sf, "r") as f:
            sql_content = f.read()
        logger.info("Applying %s...", sf)
        client.query(sql_content).result()
        logger.info("Successfully applied %s", sf)

    # 4. Call all 5 stored procedures
    procs = [
        "sp_sync_curated_audit_events",
        "sp_sync_notebook_session_metrics",
        "sp_sync_ai_usage_metrics",
        "sp_aggregate_daily_compute_metrics",
        "sp_rollup_monthly_usage",
    ]
    for p in procs:
        logger.info("Calling %s()...", p)
        client.query(f"CALL `{HUB_PROJECT}.hub_telemetry.{p}`()").result()
        logger.info("Completed %s", p)

    # 4b. Sync storage volume metrics
    try:
        from scripts.etl.sync_storage_metrics import main as sync_storage_main
        logger.info("Syncing storage volume metrics into ops_daily_compute_metrics...")
        sync_storage_main()
    except Exception as e:
        logger.warning("Could not sync storage metrics: %s", e)

    # 5. Verification queries
    curated_count = list(client.query(f"SELECT COUNT(1) as cnt FROM `{HUB_PROJECT}.hub_telemetry.ops_audit_events_curated`").result())[0]["cnt"]
    nb_sessions_count = list(client.query(f"SELECT COUNT(1) as cnt FROM `{HUB_PROJECT}.hub_telemetry.ops_notebook_sessions`").result())[0]["cnt"]
    daily_rows = list(client.query(f"SELECT * FROM `{HUB_PROJECT}.hub_telemetry.ops_daily_compute_metrics` LIMIT 5").result())
    monthly_rows = list(client.query(f"SELECT * FROM `{HUB_PROJECT}.hub_telemetry.ops_monthly_usage_rollup` LIMIT 5").result())

    logger.info("ops_audit_events_curated count: %d", curated_count)
    logger.info("ops_notebook_sessions count: %d", nb_sessions_count)
    logger.info("ops_daily_compute_metrics sample rows: %d", len(daily_rows))
    for r in daily_rows:
        logger.info("Daily Metric Row: %s", dict(r))
    logger.info("ops_monthly_usage_rollup sample rows: %d", len(monthly_rows))
    for r in monthly_rows:
        logger.info("Monthly Rollup Row: %s", dict(r))


if __name__ == "__main__":
    main()
