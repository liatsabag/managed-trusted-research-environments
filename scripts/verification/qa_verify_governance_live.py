"""QA Tester Empirical Verification Script for Governance Implementation in LIVE GCP.

Performs direct queries to Google Cloud BigQuery API and Google Cloud Storage API,
as well as invoking ComplianceService methods.
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import sys
import json
from datetime import date, datetime
from google.cloud import bigquery, storage
from backend.app.services.compliance import get_compliance_service, ComplianceService
from backend.app.models.compliance import OnboardingGateRequest, GateDecision, RoomOverallCompliance

PROJECT_ID = "gcp-rr-hub-core"
DATASET_ID = "hub_telemetry"
CHECKLIST_TABLE = "ops_regulatory_checklist"
REQUESTS_TABLE = "ops_room_requests"
BUCKET_NAME = "gcp-rr-hub-approvals"

def verify_live_gcp():
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": {
            "project_id": PROJECT_ID,
            "dataset": f"{PROJECT_ID}.{DATASET_ID}",
            "checklist_table": f"{PROJECT_ID}.{DATASET_ID}.{CHECKLIST_TABLE}",
            "requests_table": f"{PROJECT_ID}.{DATASET_ID}.{REQUESTS_TABLE}",
            "bucket_name": f"gs://{BUCKET_NAME}",
        },
        "tasks": {},
        "overall_pass": True,
        "failures": []
    }

    bq_client = bigquery.Client(project=PROJECT_ID)
    storage_client = storage.Client(project=PROJECT_ID)

    # ==========================================
    # Task 1: BigQuery Regulatory Checklist Verification
    # ==========================================
    print("\n--- Task 1: BigQuery Regulatory Checklist Verification ---")
    t1_results = {"passed": True, "details": {}}
    
    query_prov = f"""
    SELECT room_id, room_type, item_type, item_name, status, approval_date, expiration_date, approver_name, document_uri
    FROM `{PROJECT_ID}.{DATASET_ID}.{CHECKLIST_TABLE}`
    WHERE room_type = 'PROVISIONED'
    ORDER BY room_id, item_type
    """
    rows_prov = [dict(r) for r in bq_client.query(query_prov).result()]
    t1_results["details"]["provisioned_row_count"] = len(rows_prov)
    t1_results["details"]["provisioned_rows"] = rows_prov

    # Check 1.1: Exactly 20 rows across the 4 active rooms
    active_rooms = {"rr-oncology-01", "rr-genomics-02", "rr-cardio-03", "rr-neurology-04"}
    prov_rooms = set(r["room_id"] for r in rows_prov)
    if len(rows_prov) != 20:
        msg = f"Task 1 Failure: Expected 20 PROVISIONED rows, got {len(rows_prov)}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    elif prov_rooms != active_rooms:
        msg = f"Task 1 Failure: Expected rooms {active_rooms}, got {prov_rooms}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ PROVISIONED row count is exactly 20 across the 4 active rooms: {sorted(list(prov_rooms))}")

    # Check 1.2: All 20 active rows have status = 'Approved' and expiration dates > 2027
    non_approved = [r for r in rows_prov if r["status"] != "Approved"]
    non_future = []
    for r in rows_prov:
        exp = str(r["expiration_date"])
        # parse year
        try:
            exp_year = int(exp.split("-")[0])
            if exp_year < 2027:
                non_future.append(r)
        except Exception:
            non_future.append(r)

    if non_approved:
        msg = f"Task 1 Failure: Found non-Approved PROVISIONED items: {non_approved}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    elif non_future:
        msg = f"Task 1 Failure: Found expiration <= 2027: {non_future}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print("✅ All 20 PROVISIONED rows have status='Approved' and expiration dates in the future (> 2027).")

    # Check 1.3: room_type = 'PENDING_REQUEST' exactly 10 rows across 2 prospective rooms
    query_pend = f"""
    SELECT room_id, room_type, item_type, item_name, status, approval_date, expiration_date, approver_name, document_uri
    FROM `{PROJECT_ID}.{DATASET_ID}.{CHECKLIST_TABLE}`
    WHERE room_type = 'PENDING_REQUEST'
    ORDER BY room_id, item_type
    """
    rows_pend = [dict(r) for r in bq_client.query(query_pend).result()]
    t1_results["details"]["pending_row_count"] = len(rows_pend)
    t1_results["details"]["pending_rows"] = rows_pend
    
    pend_rooms = set(r["room_id"] for r in rows_pend)
    expected_pend_rooms = {"rr-immunology-05", "rr-pediatrics-06"}
    if len(rows_pend) != 10:
        msg = f"Task 1 Failure: Expected 10 PENDING_REQUEST rows, got {len(rows_pend)}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    elif pend_rooms != expected_pend_rooms:
        msg = f"Task 1 Failure: Expected pending rooms {expected_pend_rooms}, got {pend_rooms}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ PENDING_REQUEST row count is exactly 10 across the 2 prospective rooms: {sorted(list(pend_rooms))}")

    # Check 1.4: rr-immunology-05 has 4 Approved and 1 Missing (Data_Transfer)
    imm_rows = [r for r in rows_pend if r["room_id"] == "rr-immunology-05"]
    imm_approved = [r for r in imm_rows if r["status"] == "Approved"]
    imm_missing = [r for r in imm_rows if r["status"] == "Missing"]
    if len(imm_approved) != 4 or len(imm_missing) != 1 or imm_missing[0]["item_type"] != "Data_Transfer":
        msg = f"Task 1 Failure: rr-immunology-05 items unexpected: approved={len(imm_approved)}, missing={imm_missing}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ rr-immunology-05 has exactly 4 Approved and 1 Missing (Data_Transfer: {imm_missing[0]['item_name']})")

    # Check 1.5: rr-pediatrics-06 has 4 Approved and 1 Expired (Helsinki_IRB on 2026-06-30)
    ped_rows = [r for r in rows_pend if r["room_id"] == "rr-pediatrics-06"]
    ped_approved = [r for r in ped_rows if r["status"] == "Approved"]
    ped_expired = [r for r in ped_rows if r["status"] == "Expired"]
    if len(ped_approved) != 4 or len(ped_expired) != 1 or ped_expired[0]["item_type"] != "Helsinki_IRB" or str(ped_expired[0]["expiration_date"]) != "2026-06-30":
        msg = f"Task 1 Failure: rr-pediatrics-06 items unexpected: approved={len(ped_approved)}, expired={ped_expired}"
        report["failures"].append(msg)
        t1_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ rr-pediatrics-06 has exactly 4 Approved and 1 Expired (Helsinki_IRB expiring {ped_expired[0]['expiration_date']})")

    report["tasks"]["task_1_checklist"] = t1_results

    # ==========================================
    # Task 2: BigQuery Room Requests Verification
    # ==========================================
    print("\n--- Task 2: BigQuery Room Requests Verification ---")
    t2_results = {"passed": True, "details": {}}
    
    query_reqs = f"""
    SELECT request_id, proposed_room_id, room_name, main_researcher, purpose_of_research,
           location, expected_funds_usd, expected_time_range, gate_decision, missing_items,
           expired_items, warning_items, summary_reason, scanned_at, created_at
    FROM `{PROJECT_ID}.{DATASET_ID}.{REQUESTS_TABLE}`
    ORDER BY request_id
    """
    rows_reqs = [dict(r) for r in bq_client.query(query_reqs).result()]
    t2_results["details"]["room_requests"] = rows_reqs
    t2_results["details"]["count"] = len(rows_reqs)

    # Check 2.1: Exactly 2 rows (req-immunology-05 and req-pediatrics-06)
    req_ids = [r["request_id"] for r in rows_reqs]
    if len(rows_reqs) != 2 or set(req_ids) != {"req-immunology-05", "req-pediatrics-06"}:
        msg = f"Task 2 Failure: Expected req-immunology-05 and req-pediatrics-06, got {req_ids}"
        report["failures"].append(msg)
        t2_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ Exactly 2 room requests found: {req_ids}")

    # Check 2.2: gate_decision = 'GATE_BLOCKED' for both rows
    blocked_reqs = [r for r in rows_reqs if r["gate_decision"] == "GATE_BLOCKED"]
    if len(blocked_reqs) != 2:
        msg = f"Task 2 Failure: Not all requests are GATE_BLOCKED: {[(r['request_id'], r['gate_decision']) for r in rows_reqs]}"
        report["failures"].append(msg)
        t2_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print("✅ gate_decision = 'GATE_BLOCKED' for both prospective room requests.")

    # Check 2.3: Non-empty missing_items for req-immunology-05 and expired_items for req-pediatrics-06
    imm_req = next((r for r in rows_reqs if r["request_id"] == "req-immunology-05"), None)
    ped_req = next((r for r in rows_reqs if r["request_id"] == "req-pediatrics-06"), None)

    if not imm_req or 'Data_Transfer' not in imm_req.get("missing_items", ""):
        msg = f"Task 2 Failure: req-immunology-05 missing_items unexpected: {imm_req.get('missing_items') if imm_req else 'None'}"
        report["failures"].append(msg)
        t2_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ req-immunology-05 has expected missing_items: {imm_req['missing_items']}")

    if not ped_req or 'Helsinki_IRB' not in ped_req.get("expired_items", ""):
        msg = f"Task 2 Failure: req-pediatrics-06 expired_items unexpected: {ped_req.get('expired_items') if ped_req else 'None'}"
        report["failures"].append(msg)
        t2_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ req-pediatrics-06 has expected expired_items: {ped_req['expired_items']}")

    # Check 2.4: scanned_at populated with valid recent timestamp
    for r in rows_reqs:
        scanned_at = r.get("scanned_at")
        if not scanned_at:
            msg = f"Task 2 Failure: scanned_at is empty for {r['request_id']}"
            report["failures"].append(msg)
            t2_results["passed"] = False
            print(f"❌ {msg}")
        else:
            print(f"✅ {r['request_id']} has valid scanned_at timestamp: {scanned_at}")

    report["tasks"]["task_2_room_requests"] = t2_results

    # ==========================================
    # Task 3: Cloud Storage Approvals Bucket Verification
    # ==========================================
    print("\n--- Task 3: Cloud Storage Approvals Bucket Verification ---")
    t3_results = {"passed": True, "details": {}}
    
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs())
    txt_blobs = [b.name for b in blobs if b.name.endswith(".txt")]
    
    folder_counts = {}
    for name in txt_blobs:
        parts = name.split("/")
        if len(parts) >= 2:
            folder = parts[0]
            folder_counts[folder] = folder_counts.get(folder, 0) + 1

    t3_results["details"]["total_txt_files"] = len(txt_blobs)
    t3_results["details"]["folder_counts"] = folder_counts
    t3_results["details"]["all_txt_files"] = txt_blobs

    expected_counts = {
        "rr-oncology-01": 5,
        "rr-genomics-02": 5,
        "rr-cardio-03": 5,
        "rr-neurology-04": 5,
        "rr-immunology-05": 4,
        "rr-pediatrics-06": 5,
    }

    if len(txt_blobs) != 29:
        msg = f"Task 3 Failure: Expected 29 .txt files in gs://{BUCKET_NAME}, got {len(txt_blobs)}"
        report["failures"].append(msg)
        t3_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ Exactly 29 .txt files exist in gs://{BUCKET_NAME}")

    folder_match = True
    for folder, count in expected_counts.items():
        actual = folder_counts.get(folder, 0)
        if actual != count:
            msg = f"Task 3 Failure: Folder {folder} expected {count} files, got {actual}"
            report["failures"].append(msg)
            t3_results["passed"] = False
            folder_match = False
            print(f"❌ {msg}")
        else:
            print(f"✅ Folder '{folder}' has exactly {actual} approval document files.")

    report["tasks"]["task_3_storage_bucket"] = t3_results

    # ==========================================
    # Task 4: Live End-to-End Compliance Service Verification
    # ==========================================
    print("\n--- Task 4: Live End-to-End Compliance Service Verification ---")
    t4_results = {"passed": True, "details": {}}

    svc = get_compliance_service()
    
    # Test 4.1: get_room_compliance for all 4 active rooms
    active_summaries = {}
    for r_id in ["rr-oncology-01", "rr-genomics-02", "rr-cardio-03", "rr-neurology-04"]:
        summary = svc.get_room_compliance(r_id)
        active_summaries[r_id] = {
            "room_id": summary.room_id,
            "overall_status": summary.overall_status.value,
            "min_days_remaining": summary.min_days_remaining,
            "iam_state": summary.iam_state,
            "item_count": len(summary.items),
            "approved_count": len([i for i in summary.items.values() if i.status.value == "Approved"]),
        }
        if summary.overall_status != RoomOverallCompliance.COMPLIANT or len(summary.items) != 5:
            msg = f"Task 4 Failure: Room {r_id} compliance summary is not COMPLIANT (5 items): {summary.overall_status.value}"
            report["failures"].append(msg)
            t4_results["passed"] = False
            print(f"❌ {msg}")
        else:
            print(f"✅ get_room_compliance('{r_id}'): Status={summary.overall_status.value}, Items={len(summary.items)}/5 Approved, MinDays={summary.min_days_remaining}")

    t4_results["details"]["active_rooms"] = active_summaries

    # Test 4.2: evaluate_onboarding_gate for prospective requests
    gate_evals = {}
    
    # 4.2.a: req-immunology-05
    imm_gate_req = OnboardingGateRequest(
        request_id="req-immunology-05",
        proposed_room_id="rr-immunology-05",
        document_bucket_uri="gs://gcp-rr-hub-approvals/rr-immunology-05",
    )
    imm_gate_res = svc.evaluate_onboarding_gate(imm_gate_req)
    gate_evals["req-immunology-05"] = {
        "gate_decision": imm_gate_res.gate_decision.value,
        "missing_items": imm_gate_res.missing_items,
        "expired_items": imm_gate_res.expired_items,
        "summary_reason": imm_gate_res.summary_reason,
    }
    if imm_gate_res.gate_decision != GateDecision.GATE_BLOCKED or "Data_Transfer" not in imm_gate_res.missing_items:
        msg = f"Task 4 Failure: evaluate_onboarding_gate for req-immunology-05 failed. Decision: {imm_gate_res.gate_decision.value}, Missing: {imm_gate_res.missing_items}"
        report["failures"].append(msg)
        t4_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ evaluate_onboarding_gate('req-immunology-05'): Decision={imm_gate_res.gate_decision.value}, Missing={imm_gate_res.missing_items}")

    # 4.2.b: req-pediatrics-06
    ped_gate_req = OnboardingGateRequest(
        request_id="req-pediatrics-06",
        proposed_room_id="rr-pediatrics-06",
        document_bucket_uri="gs://gcp-rr-hub-approvals/rr-pediatrics-06",
    )
    ped_gate_res = svc.evaluate_onboarding_gate(ped_gate_req)
    gate_evals["req-pediatrics-06"] = {
        "gate_decision": ped_gate_res.gate_decision.value,
        "missing_items": ped_gate_res.missing_items,
        "expired_items": ped_gate_res.expired_items,
        "summary_reason": ped_gate_res.summary_reason,
    }
    if ped_gate_res.gate_decision != GateDecision.GATE_BLOCKED or "Helsinki_IRB" not in ped_gate_res.expired_items:
        msg = f"Task 4 Failure: evaluate_onboarding_gate for req-pediatrics-06 failed. Decision: {ped_gate_res.gate_decision.value}, Expired: {ped_gate_res.expired_items}"
        report["failures"].append(msg)
        t4_results["passed"] = False
        print(f"❌ {msg}")
    else:
        print(f"✅ evaluate_onboarding_gate('req-pediatrics-06'): Decision={ped_gate_res.gate_decision.value}, Expired={ped_gate_res.expired_items}")

    t4_results["details"]["gate_evaluations"] = gate_evals
    report["tasks"]["task_4_compliance_service"] = t4_results

    # ==========================================
    # Final QA Assessment
    # ==========================================
    report["overall_pass"] = len(report["failures"]) == 0
    print("\n========================================================")
    print(f"FINAL QA RESULT: {'PASSED (100% OK)' if report['overall_pass'] else 'FAILED'}")
    print("========================================================")
    
    with open("qa_verification_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    return report

if __name__ == "__main__":
    rep = verify_live_gcp()
    if not rep["overall_pass"]:
        sys.exit(1)
