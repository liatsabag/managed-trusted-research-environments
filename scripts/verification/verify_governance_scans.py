"""Live verification script for Mode 1 (Continuous Room Scan) and Mode 2 (On-Demand Onboarding Gate Scan)."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
from google.cloud import bigquery
from backend.app.services.compliance import get_compliance_service
from backend.app.services.fleet import get_fleet_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("verify_governance_scans")


def run_governance_verification():
    logger.info("Initializing Fleet & Compliance Services...")
    compliance_service = get_compliance_service()
    fleet_service = get_fleet_service()

    # 1. Execute Mode 1: Continuous Compliance Scan for all 4 Active Research Rooms
    logger.info("--- Executing Mode 1: Continuous Governance Scan on Active Fleet ---")
    active_rooms = fleet_service.list_rooms()
    mode1_results = []
    for room in active_rooms:
        res = compliance_service.scan_room_compliance(room.room_id)
        mode1_results.append({
            "room_id": res.room_id,
            "scanned_documents": res.scanned_documents_count,
            "previous_iam_state": res.previous_iam_state,
            "new_iam_state": res.new_iam_state,
            "action_taken": res.action_taken,
            "message": res.message,
        })
        logger.info("Mode 1 scan for %s: %s (IAM: %s)", res.room_id, res.message, res.new_iam_state)

    # 2. Execute Mode 2: On-Demand Pre-Flight Onboarding Gate Scan on Prospective Requests
    logger.info("--- Executing Mode 2: On-Demand Pre-Flight Onboarding Gate Scan ---")
    mode2_results = compliance_service.scan_all_prospective_requests()
    mode2_summary = []
    for gate_res in mode2_results:
        mode2_summary.append({
            "request_id": gate_res.request_id,
            "gate_decision": gate_res.gate_decision.value,
            "missing_items": gate_res.missing_items,
            "expired_items": gate_res.expired_items,
            "warning_items": gate_res.warning_items,
            "summary_reason": gate_res.summary_reason,
            "evaluated_at": gate_res.evaluated_at,
        })
        logger.info("Mode 2 gate scan for %s: Decision=%s, Reason=%s",
                    gate_res.request_id, gate_res.gate_decision.value, gate_res.summary_reason)

    # 3. Query Live BigQuery to Verify Persistence
    bq_client = bigquery.Client(project=compliance_service.settings.GCP_PROJECT_ID)
    
    # Check ops_regulatory_checklist
    chk_query = f"""
    SELECT room_id, room_type, item_type, status, expiration_date, comments
    FROM `{compliance_service.settings.GCP_PROJECT_ID}.hub_telemetry.ops_regulatory_checklist`
    ORDER BY room_type, room_id, item_type
    """
    chk_rows = [dict(row) for row in bq_client.query(chk_query).result()]

    # Check ops_room_requests
    req_query = f"""
    SELECT request_id, proposed_room_id, room_name, main_researcher, purpose_of_research,
           location, expected_funds_usd, expected_time_range, gate_decision, missing_items,
           expired_items, summary_reason, scanned_at
    FROM `{compliance_service.settings.GCP_PROJECT_ID}.hub_telemetry.ops_room_requests`
    ORDER BY request_id
    """
    req_rows = [dict(row) for row in bq_client.query(req_query).result()]

    output = {
        "mode1_active_scans": mode1_results,
        "mode2_gate_scans": mode2_summary,
        "bigquery_ops_regulatory_checklist_count": len(chk_rows),
        "bigquery_ops_regulatory_checklist": chk_rows,
        "bigquery_ops_room_requests": req_rows,
    }

    print("\n================ GOVERNANCE VERIFICATION SUMMARY ================")
    print(json.dumps(output, indent=2, default=str))
    return output


if __name__ == "__main__":
    run_governance_verification()
