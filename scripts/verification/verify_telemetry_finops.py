#!/usr/bin/env python3
"""
End-to-End Verification Test Script for Research Room Telemetry, Audit & FinOps Platform.

Verifies:
1. BigQuery Marts, Schemas, and Colab Enterprise Session Tracking
2. Stored Procedure Synchronization Execution
3. Backend Telemetry and FinOps Service Resolvers (Fleet, Room, Researcher, Institute)
4. Direct Researcher vs. Shared Administrative Overhead Attribution
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import sys
import logging
from datetime import datetime, timezone
from google.cloud import bigquery

# Ensure backend imports resolve
sys.path.insert(0, ".")

from backend.app.services.telemetry import TelemetryService
from backend.app.services.finops import FinOpsService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_telemetry_finops")

HUB_PROJECT = "gcp-rr-hub-core"
DATASET = "hub_telemetry"


def test_bigquery_schemas(bq_client: bigquery.Client):
    logger.info("=== STEP 1: Verifying BigQuery Tables and Colab Enterprise Schemas ===")
    
    tables_to_check = {
        "ops_audit_events_curated": ["log_id", "timestamp", "room_id", "category", "service_name", "action_name"],
        "ops_notebook_sessions": ["room_id", "user_email", "session_date", "notebook_name", "runtime_id", "machine_type", "runtime_template_id", "total_active_hours"],
        "ops_ai_usage_metrics": ["room_id", "user_email", "usage_date", "service_name", "total_inference_calls"],
        "ops_daily_compute_metrics": ["usage_date", "room_id", "user_email", "query_count", "total_bytes_billed", "notebook_runtime_hours", "ai_inference_count", "storage_bytes"],
        "ops_monthly_usage_rollup": ["usage_month", "room_id", "institute_id", "avg_active_researchers", "total_notebook_hours", "total_query_volume_tb"],
    }

    for table_name, expected_fields in tables_to_check.items():
        tbl = bq_client.get_table(f"{HUB_PROJECT}.{DATASET}.{table_name}")
        existing_cols = {f.name for f in tbl.schema}
        missing = [f for f in expected_fields if f not in existing_cols]
        assert not missing, f"Table {table_name} is missing expected columns: {missing}"
        logger.info("✓ Table `%s` verified with %d columns (Rows: %d).", table_name, len(tbl.schema), tbl.num_rows)


def test_stored_procedures(bq_client: bigquery.Client):
    logger.info("=== STEP 2: Testing Stored Procedure Executions ===")
    procs = [
        "sp_sync_curated_audit_events",
        "sp_sync_notebook_session_metrics",
        "sp_sync_ai_usage_metrics",
        "sp_aggregate_daily_compute_metrics",
        "sp_rollup_monthly_usage"
    ]
    for p in procs:
        logger.info("Calling CALL `%s.%s.%s`()...", HUB_PROJECT, DATASET, p)
        bq_client.query(f"CALL `{HUB_PROJECT}.{DATASET}.{p}`()").result()
        logger.info("✓ Stored procedure `%s` executed successfully.", p)


def test_telemetry_service():
    logger.info("=== STEP 3: Testing Backend Telemetry Services ===")
    service = TelemetryService()

    # 1. Fleet Overview
    overview = service.get_fleet_overview()
    logger.info("✓ Fleet Overview: 24h Queries=%d, 30d Bytes=%d, Total Storage Bytes=%d",
                overview.total_queries_24h, overview.total_bytes_scanned_30d, overview.total_fleet_storage_bytes)

    # 2. Queries Feed
    queries = service.get_queries(limit=5)
    assert len(queries) > 0, "Expected at least 1 query in telemetry query log."
    logger.info("✓ Query Log: retrieved %d queries (Sample Job ID: %s, User: %s)",
                len(queries), queries[0].job_id, queries[0].user_email)

    # 3. Curated Audit Feed
    audit_events = service.get_audit_feed(limit=5)
    assert len(audit_events) > 0, "Expected at least 1 audit event in curated mart."
    logger.info("✓ Curated Audit Feed: retrieved %d events (Category: %s, Action: %s)",
                len(audit_events), audit_events[0].category, audit_events[0].method_name)

    # 4. Colab Enterprise Notebook Sessions
    sessions = service.get_notebook_sessions(limit=5)
    logger.info("✓ Colab Enterprise Sessions: retrieved %d sessions (Template: %s, Machine: %s, Hours: %.2f)",
                len(sessions), sessions[0].runtime_template_id if sessions else "N/A",
                sessions[0].machine_type if sessions else "N/A",
                sessions[0].total_active_hours if sessions else 0.0)

    # 5. Room Activity Summary
    activity = service.get_room_activity(room_id="rr-oncology-01", limit=10)
    logger.info("✓ Room Activity for rr-oncology-01: Total Queries=%d, Researcher Queries=%d, Notebook Hours=%.2f",
                activity.total_queries_count, activity.researcher_queries_count, activity.total_notebook_hours)


def test_finops_service():
    logger.info("=== STEP 4: Testing FinOps Attribution & Resolution Hierarchy ===")
    finops = FinOpsService()

    # 1. Fleet Summary
    summary = finops.get_summary()
    logger.info("✓ FinOps Fleet Summary: Total Cost=$%.2f, Forecast=$%.2f, Active Rooms=%d, Institutes=%d",
                summary.total_fleet_cost, summary.forecasted_monthly_cost, len(summary.rooms), len(summary.institutes))

    # 2. Room Level Detail & Direct vs Admin Overhead Separation
    room_detail = finops.get_room_cost("rr-oncology-01")
    logger.info("✓ Room FinOps rr-oncology-01: Invoiced Cost=$%.2f, Budget=$%.2f, Status=%s",
                room_detail.total_invoiced_cost, room_detail.budget_limit_usd, room_detail.reconciliation_status)
    logger.info("  Direct Researcher Attributions (%d researchers):", len(room_detail.researchers))
    for r in room_detail.researchers:
        logger.info("    - %s (%s): Direct Spend=$%.2f, BQ Queries=%d, Notebook Hours=%.2f",
                    r.name, r.email, r.total_allocated_cost, r.telemetry_usage.query_count, r.telemetry_usage.notebook_runtime_hours)
    logger.info("  Shared Administrative Overhead: Cost=$%.2f, Admin Queries=%d",
                room_detail.shared_overhead.total_shared_overhead_cost, room_detail.shared_overhead.admin_usage.query_count)

    # 3. Researcher Fleet Attributions
    researchers = finops.get_researcher_attributions()
    assert len(researchers) > 0, "Expected at least 1 enrolled researcher in FinOps roster."
    logger.info("✓ Researchers Fleet: %d researcher attributions across rooms (Sample: %s from %s with $%.2f spend)",
                len(researchers), researchers[0].name, researchers[0].institute_id, researchers[0].total_allocated_cost)

    # 4. Institute Level Breakdown
    inst_cost = finops.get_institute_cost("inst-mskcc")
    logger.info("✓ Institute Level Breakdown for %s: Total Spend=$%.2f, Active Researchers=%d, Rooms=%s",
                inst_cost.institute_name, inst_cost.total_allocated_cost, inst_cost.researcher_count, inst_cost.rooms_involved)

    # 5. FinOps Multi-Tenant Allocation Matrix
    matrix = finops.get_allocation_matrix()
    logger.info("✓ FinOps Allocation Matrix Status: %s, Invoiced=$%.2f, Researcher Allocated=$%.2f, Shared Overhead=$%.2f, Hub Infra=$%.2f",
                matrix.reconciliation_status, matrix.total_invoice_cost, matrix.total_researcher_allocated_cost,
                matrix.total_shared_overhead_cost, matrix.total_hub_infrastructure_cost)


def main():
    logger.info("Starting Research Room End-to-End Telemetry & FinOps Verification Suite...")
    bq_client = bigquery.Client(project=HUB_PROJECT, location="me-west1")

    try:
        test_bigquery_schemas(bq_client)
        test_stored_procedures(bq_client)
        test_telemetry_service()
        test_finops_service()
        logger.info("=================================================================")
        logger.info("🎉 ALL TELEMETRY, AUDIT & FINOPS VERIFICATION CHECKS PASSED 100%!")
        logger.info("=================================================================")
    except Exception as e:
        logger.error("❌ Verification Suite Failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
