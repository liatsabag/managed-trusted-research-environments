"""Verification script for FinOps multi-room attribution, storage weighting, shared overhead, and $0.00 reconciliation."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import logging
from backend.app.services.finops import FinOpsService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    svc = FinOpsService()
    summary = svc.get_summary(invoice_month="202609")
    
    print("\n" + "=" * 95)
    print("                GCP RESEARCH ROOM FINOPS COST RECONCILIATION REPORT (202609)")
    print("=" * 95)
    print(f"Total Fleet Invoiced Cost:         ${summary.total_fleet_cost:>10.2f} USD")
    print(f"  ├─ Central Hub Infrastructure:   ${summary.hub_infrastructure_cost:>10.2f} USD")
    print(f"  ├─ Total Researcher Allocated:   ${summary.total_researcher_cost:>10.2f} USD")
    print(f"  └─ Total Room Shared Overhead:   ${summary.total_shared_overhead_cost:>10.2f} USD")
    
    reconciled_sum = summary.total_researcher_cost + summary.total_shared_overhead_cost + summary.hub_infrastructure_cost
    drift = abs(summary.total_fleet_cost - reconciled_sum)
    print(f"Fleet Reconciliation Drift:        ${drift:>10.4f} USD ({'BALANCED' if drift < 0.05 else 'DISCREPANCY'})")
    print("=" * 95)
    
    print("\n" + "-" * 95)
    print(f"{'Room ID':<18} | {'Spoke Project':<26} | {'Invoiced':<9} | {'Researchers':<11} | {'Overhead':<9} | {'Drift'}")
    print("-" * 95)
    for rm in summary.rooms:
        rm_rec = rm.total_researcher_allocated_cost + rm.room_shared_overhead_cost
        rm_drift = abs(rm.total_invoiced_cost - rm_rec)
        print(f"{rm.room_id:<18} | {rm.spoke_project_id:<26} | ${rm.total_invoiced_cost:>7.2f} | ${rm.total_researcher_allocated_cost:>9.2f} | ${rm.room_shared_overhead_cost:>7.2f} | ${rm_drift:.4f}")
    print("-" * 95)
    
    print("\n" + "=" * 95)
    print("                          DETAILED ROOM & RESEARCHER ATTRIBUTIONS")
    print("=" * 95)
    for rm in summary.rooms:
        print(f"\n[Room: {rm.room_id} - {rm.room_name}] ({rm.spoke_project_id})")
        print(f"Total Invoiced Cost: ${rm.total_invoiced_cost:.2f} USD")
        print(f"Room Shared / Admin Overhead: ${rm.room_shared_overhead_cost:.2f} USD")
        
        print("\n  Overhead SKU Breakdown:")
        for o_sku in rm.overhead_sku_breakdown:
            print(f"    - [{o_sku.service_description}] {o_sku.sku_description}: ${o_sku.cost:.2f} (Weight: {o_sku.weight:.2%})")
            
        print("\n  Active Researchers Cost Allocation:")
        for r in rm.researchers:
            print(f"    * Researcher: {r.first_name} {r.last_name} ({r.user_email})")
            print(f"      Allocated Cost: ${r.total_cost:.2f} USD")
            print(f"      Usage Metrics:  Bytes Billed: {r.metrics_summary.get('bytes_billed', 0):,} B | Queries: {r.metrics_summary.get('query_count', 0)} | Storage: {r.metrics_summary.get('storage_bytes', 0):,} B | AI Tokens: {r.metrics_summary.get('ai_tokens', 0):,}")
            print("      SKU Line Items:")
            for s in r.sku_breakdown:
                print(f"        - [{s.service_description}] {s.sku_description}: ${s.cost:.2f} (Weight: {s.weight:.2%})")

    print("\n" + "=" * 95)
    print("                                ALLOCATION MATRIX VERIFICATION")
    print("=" * 95)
    matrix_resp = svc.get_allocation_matrix("202609")
    print(f"Reconciliation Status: {matrix_resp.reconciliation_status}")
    print(f"Total Invoice Cost:    ${matrix_resp.total_invoice_cost:.2f}")
    print(f"Total Allocated Cost:  ${matrix_resp.total_allocated_cost:.2f}")
    print(f"Total Shared Overhead: ${matrix_resp.total_shared_overhead_cost:.2f}")
    print(f"Total Hub Infra Cost:  ${matrix_resp.total_hub_infrastructure_cost:.2f}")
    print(f"Variance:              ${matrix_resp.variance:.4f}")
    print("=" * 95)

if __name__ == "__main__":
    main()
