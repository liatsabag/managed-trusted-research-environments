#!/usr/bin/env python3
"""End-to-End Verification Script for FinOps & Telemetry Attribution Pipeline."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import logging
from backend.app.services.finops import get_finops_service
from backend.app.services.reports import ReportsService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_finops")

def main():
    logger.info("==================================================")
    logger.info("   FINOPS END-TO-END CAPABILITY VERIFICATION      ")
    logger.info("==================================================")

    # 1. Test FinOpsService Summary
    finops = get_finops_service()
    logger.info("1. Executing FinOpsService.get_summary()...")
    summary = finops.get_summary()

    logger.info("-> Total Invoiced Fleet Spend: $%.2f", summary.total_fleet_cost)
    logger.info("-> Direct Researcher Spend:    $%.2f", summary.total_researcher_cost)
    logger.info("-> Shared Overhead Spend:      $%.2f", summary.total_shared_overhead_cost)
    logger.info("-> Central Hub Core Spend:     $%.2f", summary.hub_infrastructure_cost)
    logger.info("-> Active Anomaly Alerts:      %d", len(summary.anomaly_alerts))
    logger.info("-> Active Rooms Tracked:       %d", len(summary.rooms))
    logger.info("-> Active Institutes:          %d", len(summary.institutes))

    # Assert Ground-Truth Billing SSOT ($11.63 total)
    assert abs(summary.total_fleet_cost - 11.63) < 0.05, f"Expected total fleet cost ~$11.63, got {summary.total_fleet_cost}"

    # 2. Check Cost Drivers (Service-Level)
    cd = summary.cost_drivers
    logger.info("2. Service-Level Cost Drivers Aggregation:")
    logger.info("   • BigQuery:             $%.2f", cd.bigquery_cost)
    logger.info("   • Vertex AI / Gemini:   $%.2f", cd.vertex_ai_cost)
    logger.info("   • Cloud Storage:        $%.2f", cd.storage_cost)
    logger.info("   • Compute / Notebooks:  $%.2f", cd.compute_notebooks_cost)
    logger.info("   • Network / Egress:     $%.2f", cd.network_egress_cost)
    logger.info("   • Other:                $%.2f", cd.other_cost)

    # 3. Check Capacity Metrics
    cap = summary.capacity
    logger.info("3. Operational Usage Telemetry Metrics:")
    logger.info("   • BigQuery Scanned:     %.2f GB", cap.bigquery_bytes_scanned / (1024**3))
    logger.info("   • BigQuery Slot Hours:  %.4f hrs", cap.bigquery_slot_hours)
    logger.info("   • Compute Core Hours:   %.2f hrs", cap.compute_core_hours)
    logger.info("   • AI Tokens:            %d", cap.ai_token_count)
    logger.info("   • AI Inference Calls:   %d", cap.ai_calls_count)

    # 4. Verify Zero-Drift Reconciliation for Each Room
    logger.info("4. Room Reconciliation & Attribution Invariants:")
    for r in summary.rooms:
        res_sum = sum(u.total_allocated_cost for u in r.researchers)
        ovh = r.shared_overhead.total_shared_overhead_cost
        logger.info(
            "   Room [%s] Total=$%.2f | ResAlloc=$%.2f | SharedOvh=$%.2f | Status=%s (Variance=$%.4f)",
            r.room_id, r.total_invoiced_cost, res_sum, ovh, r.reconciliation_status, r.reconciliation_variance
        )
        assert r.reconciliation_status == "BALANCED", f"Room {r.room_id} has unbalanced variance {r.reconciliation_variance}"
        for res in r.researchers:
            for attr in res.sku_attributions:
                if "Analysis" in attr.sku_description or "BigQuery" in attr.sku_description:
                    assert "bytes_billed" in attr.formula_applied, f"BigQuery formula must use bytes_billed, got {attr.formula_applied}"

    # 5. Verify Multi-Room Researcher Aggregation
    logger.info("5. Testing Multi-Room Researcher Aggregation...")
    researchers_emails = [
        "dr.oren.katz@liatsabag.altostrat.com",
        "prof.miriam.levy@liatsabag.altostrat.com",
        "dr.maya.lin@liatsabag.altostrat.com",
        "dr.daniel.cohen@liatsabag.altostrat.com",
    ]
    for email in researchers_emails:
        res_data = finops.get_researcher_spend(email)
        logger.info(
            "   Researcher [%s]: Total Spend=$%.4f across %d room(s)",
            res_data["name"], res_data["total_spend"], res_data["rooms_count"]
        )
        assert res_data["total_spend"] > 0, f"Researcher {email} should have positive allocated spend"

    # 6. Verify ReportsService SSOT
    logger.info("6. Testing ReportsService.get_cost_finops_report()...")
    reports_svc = ReportsService()
    rep = reports_svc.get_cost_finops_report()
    logger.info("-> Generated Report ID: %s (%d room records)", rep.metadata.report_id, rep.metadata.record_count)
    assert len(rep.records) == len(summary.rooms), "Mismatch between report record count and rooms count"

    logger.info("==================================================")
    logger.info("   ALL FINOPS VERIFICATION CHECKS PASSED (100%)   ")
    logger.info("==================================================")

if __name__ == "__main__":
    main()
