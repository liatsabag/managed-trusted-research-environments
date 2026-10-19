"""Compliance & Regulatory Checklist Service powered by BigQuery Governance."""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import get_settings
from backend.app.models.compliance import (
    ComplianceHorizonReport,
    ComplianceScanResult,
    CreateRoomRequest,
    GateDecision,
    OnboardingGateRequest,
    OnboardingGateResponse,
    RegulatoryChecklistItem,
    RegulatoryItemStatus,
    RegulatoryItemType,
    RoomComplianceSummary,
    RoomOverallCompliance,
    RoomRequestResponse,
)
from backend.app.models.rooms import DowngradeRequest
from backend.app.services.fleet import FleetGovernanceService, get_fleet_service

logger = logging.getLogger("compliance_service")

REQUIRED_PREREQUISITES = [
    (RegulatoryItemType.RESEARCH_PROTOCOL, "Scientific Research Protocol"),
    (RegulatoryItemType.HELSINKI_IRB, "Helsinki Ethics Committee / IRB Approval"),
    (RegulatoryItemType.DATA_TRANSFER, "Data Transfer Committee Statutory Sign-off"),
    (RegulatoryItemType.EXTRACTION_PROTOCOL, "De-identification & Extraction Query Protocol"),
    (RegulatoryItemType.DUA, "Multi-party Data Use Agreement"),
]


def parse_checklist_row(r: Dict[str, Any], room_id: str, room_type: str, today: date) -> Optional[RegulatoryChecklistItem]:
    """Helper to convert BigQuery or fixture row dict into a RegulatoryChecklistItem."""
    itype_str = r.get("item_type")
    try:
        itype = RegulatoryItemType(itype_str)
    except (ValueError, TypeError):
        return None

    exp_str = r.get("expiration_date")
    days_rem, is_exp = None, False
    if exp_str:
        try:
            exp_d = date.fromisoformat(str(exp_str))
            days_rem = (exp_d - today).days
            is_exp = days_rem < 0
        except ValueError:
            pass

    stat_raw = str(r.get("status", "APPROVED")).upper()
    if stat_raw == "MISSING":
        stat, is_valid = RegulatoryItemStatus.MISSING, False
    elif is_exp or stat_raw == "EXPIRED":
        stat, is_valid = RegulatoryItemStatus.EXPIRED, False
    elif stat_raw in ("APPROVED", "ACTIVE"):
        stat, is_valid = RegulatoryItemStatus.APPROVED, True
    else:
        stat, is_valid = RegulatoryItemStatus.PENDING_REVIEW, False

    return RegulatoryChecklistItem(
        item_id=r.get("item_id") or f"{room_id}-{itype.value}",
        room_id=room_id,
        room_type=room_type,
        item_type=itype,
        item_name=r.get("item_name") or itype.value,
        status=stat,
        approval_date=str(r.get("approval_date")) if r.get("approval_date") else None,
        expiration_date=str(exp_str) if exp_str else None,
        approver_name=r.get("approver_name"),
        document_uri=r.get("document_uri"),
        comments=r.get("comments") or "Audited via BigQuery Governance.",
        days_remaining=days_rem,
        is_valid=is_valid,
    )


class ComplianceService:
    """Core compliance service querying BigQuery ops_regulatory_checklist and coordinating IAM."""

    def __init__(self, fleet_service: Optional[FleetGovernanceService] = None) -> None:
        self.settings = get_settings()
        self.fleet_service = fleet_service or get_fleet_service()
        self._bq_client = self._init_bq_client()

    def _init_bq_client(self) -> Any:
        try:
            from google.cloud import bigquery
            return bigquery.Client(project=self.settings.GCP_PROJECT_ID)
        except Exception as e:
            logger.info("BigQuery client initialization note: %s", e)
            return None

    def _fetch_checklist_items(
        self, room_id: str, room_type: str = "PROVISIONED"
    ) -> Dict[str, RegulatoryChecklistItem]:
        """Fetch regulatory checklist items for a room from BigQuery ops_regulatory_checklist."""
        items: Dict[str, RegulatoryChecklistItem] = {}
        target_ids = [room_id]
        if room_id.startswith("req-"):
            target_ids.append("rr-" + room_id[4:])
        elif room_id.startswith("rr-"):
            target_ids.append("req-" + room_id[3:])

        today = date.today()

        if self._bq_client:
            try:
                ids_str = ", ".join(f"'{tid}'" for tid in target_ids)
                query = f"""
                SELECT item_id, room_id, room_type, item_type, item_name, status,
                       CAST(approval_date AS STRING) as approval_date,
                       CAST(expiration_date AS STRING) as expiration_date,
                       approver_name, document_uri, comments
                FROM `{self.settings.GCP_PROJECT_ID}.hub_telemetry.ops_regulatory_checklist`
                WHERE room_id IN ({ids_str})
                ORDER BY CASE WHEN room_type = '{room_type}' THEN 0 ELSE 1 END, last_updated DESC
                """
                for r in self._bq_client.query(query).result():
                    parsed = parse_checklist_row(dict(r), room_id, room_type, today)
                    if parsed and parsed.item_type.value not in items:
                        items[parsed.item_type.value] = parsed
            except Exception as e:
                logger.warning("BigQuery checklist read notice for %s: %s", room_id, e)

        if not items:
            items = self._load_fallback_items(room_id, target_ids, room_type, today)

        # Ensure all 5 statutory items exist
        for ptype, pname in REQUIRED_PREREQUISITES:
            if ptype.value not in items:
                items[ptype.value] = RegulatoryChecklistItem(
                    item_id=f"{room_id}-{ptype.value}", room_id=room_id, room_type=room_type,
                    item_type=ptype, item_name=pname, status=RegulatoryItemStatus.MISSING,
                    comments="Document missing in regulatory checklist.", is_valid=False,
                )
        return items

    def _load_fallback_items(
        self, room_id: str, target_ids: List[str], room_type: str, today: date
    ) -> Dict[str, RegulatoryChecklistItem]:
        """Offline fallback loader reading local staging fixtures for unit testing."""
        items: Dict[str, RegulatoryChecklistItem] = {}
        base_dir = Path(__file__).resolve().parents[3]
        staging_file = base_dir / "staging" / "bigquery" / "hub_telemetry" / "ops_regulatory_checklist.json"
        if staging_file.exists():
            try:
                with open(staging_file, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                for r in rows:
                    if r.get("room_id") in target_ids:
                        parsed = parse_checklist_row(r, room_id, room_type, today)
                        if parsed and parsed.item_type.value not in items:
                            items[parsed.item_type.value] = parsed
            except Exception as e:
                logger.debug("Fallback load note: %s", e)
        return items

    def get_room_compliance(self, room_id: str) -> RoomComplianceSummary:
        """Retrieve aggregated 5-item compliance summary for an active research room."""
        room_detail = self.fleet_service.get_room(room_id)
        room_name = room_detail.room_name if room_detail else room_id
        iam_state = room_detail.status if room_detail else "ACTIVE"

        items = self._fetch_checklist_items(room_id, room_type="PROVISIONED")
        valid_days = [it.days_remaining for it in items.values() if it.days_remaining is not None and it.is_valid]
        min_days = min(valid_days) if valid_days else None

        missing = [it for it in items.values() if it.status == RegulatoryItemStatus.MISSING]
        expired = [it for it in items.values() if it.status == RegulatoryItemStatus.EXPIRED or not it.is_valid]

        if missing:
            overall = RoomOverallCompliance.INCOMPLETE
        elif expired:
            overall = RoomOverallCompliance.NON_COMPLIANT
        elif min_days is not None and min_days <= 30:
            overall = RoomOverallCompliance.EXPIRING_SOON
        else:
            overall = RoomOverallCompliance.COMPLIANT

        return RoomComplianceSummary(
            room_id=room_id, room_name=room_name, overall_status=overall,
            items=items, min_days_remaining=min_days, iam_state=iam_state,
            last_scanned_at=datetime.now(timezone.utc).isoformat(),
        )

    def scan_room_compliance(self, room_id: str) -> ComplianceScanResult:
        """Evaluate single room compliance and enforce IAM soft-downgrade/reactivate."""
        summary = self.get_room_compliance(room_id)
        room_detail = self.fleet_service.get_room(room_id)
        prev_iam = room_detail.status if room_detail else "ACTIVE"
        action_taken, new_iam = None, prev_iam
        msg = f"Compliance verified for {room_id}. Overall status: {summary.overall_status.value}."

        if summary.overall_status in (RoomOverallCompliance.NON_COMPLIANT, RoomOverallCompliance.INCOMPLETE):
            if prev_iam != "SOFT_DOWNGRADED":
                req = DowngradeRequest(reason=f"Regulatory compliance violation: {summary.overall_status.value}")
                if self.fleet_service.downgrade_room(room_id, req):
                    action_taken, new_iam = "DOWNGRADED_TO_READONLY", "SOFT_DOWNGRADED"
                    msg = f"Compliance violation detected. Room {room_id} soft-downgraded to read-only."
                    self._update_room_registry_status(room_id, "SOFT_DOWNGRADED")
        elif summary.overall_status in (RoomOverallCompliance.COMPLIANT, RoomOverallCompliance.EXPIRING_SOON):
            if prev_iam == "SOFT_DOWNGRADED":
                if self.fleet_service.reactivate_room(room_id):
                    action_taken, new_iam = "REACTIVATED", "ACTIVE"
                    msg = f"All 5 prerequisites valid. Room {room_id} restored to ACTIVE status."
                    self._update_room_registry_status(room_id, "ACTIVE")

        return ComplianceScanResult(
            room_id=room_id,
            scanned_documents_count=len([i for i in summary.items.values() if i.status != RegulatoryItemStatus.MISSING]),
            items=summary.items, action_taken=action_taken, previous_iam_state=prev_iam,
            new_iam_state=new_iam, message=msg,
        )

    def _update_room_registry_status(self, room_id: str, new_status: str) -> None:
        """Update live reg_research_rooms table in BigQuery."""
        if self._bq_client:
            try:
                sql = f"UPDATE `{self.settings.GCP_PROJECT_ID}.hub_registry.reg_research_rooms` SET status = '{new_status}' WHERE room_id = '{room_id}'"
                self._bq_client.query(sql).result()
            except Exception as e:
                logger.warning("Failed updating room registry status in BQ: %s", e)

    def enforce_fleet_compliance(self) -> List[ComplianceScanResult]:
        """Fleet-wide IAM enforcement: iterate active provisioned rooms and sync IAM state."""
        return [self.scan_room_compliance(r.room_id) for r in self.fleet_service.list_rooms()]

    def evaluate_onboarding_gate(self, request: Any) -> OnboardingGateResponse:
        """Evaluate pre-flight onboarding gate for prospective room requests with zero IAM mutations."""
        req_id = request if isinstance(request, str) else request.request_id
        prop_id = ("rr-" + req_id[4:]) if req_id.startswith("req-") else (getattr(request, "proposed_room_id", None) or req_id)
        items = self._fetch_checklist_items(prop_id, room_type="REQUEST")

        missing = [t for t, i in items.items() if i.status == RegulatoryItemStatus.MISSING]
        expired = [t for t, i in items.items() if i.status == RegulatoryItemStatus.EXPIRED]
        warning = [t for t, i in items.items() if i.is_valid and i.days_remaining is not None and i.days_remaining <= 30]

        if missing or expired:
            decision = GateDecision.GATE_BLOCKED
            reason = f"Onboarding blocked: {len(missing)} missing prerequisite(s) and {len(expired)} expired approval(s)."
        elif warning:
            decision = GateDecision.GATE_WARNING
            reason = f"Onboarding approved with warning: {len(warning)} item(s) expiring within 30 days."
        else:
            decision = GateDecision.GATE_PASSED
            reason = "Pre-flight validation passed: all 5 prerequisite documents verified and active."

        return OnboardingGateResponse(
            request_id=req_id, gate_decision=decision, items=items,
            missing_items=missing, expired_items=expired, warning_items=warning,
            summary_reason=reason, evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_horizon_report(self) -> ComplianceHorizonReport:
        """Generate fleet-wide compliance horizon expiration forecast."""
        report = ComplianceHorizonReport()
        for room in self.fleet_service.list_rooms():
            summary = self.get_room_compliance(room.room_id)
            if summary.overall_status in (RoomOverallCompliance.NON_COMPLIANT, RoomOverallCompliance.INCOMPLETE):
                report.non_compliant_rooms.append(room.room_id)
            for item in summary.items.values():
                if item.days_remaining is not None and item.is_valid:
                    if item.days_remaining <= 30:
                        report.expiring_30_days.append(item)
                    elif item.days_remaining <= 60:
                        report.expiring_60_days.append(item)
                    elif item.days_remaining <= 90:
                        report.expiring_90_days.append(item)
        return report

    def list_all_summaries(self) -> List[RoomComplianceSummary]:
        """List compliance summaries for all active research rooms."""
        return [self.get_room_compliance(r.room_id) for r in self.fleet_service.list_rooms()]

    def get_room_requests(self) -> List[RoomRequestResponse]:
        """Fetch all prospective research room onboarding requests from BigQuery."""
        if not self._bq_client:
            return []
        table_id = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_room_requests"
        query = f"""
            SELECT request_id, proposed_room_id, room_name, institute_id, requested_by,
                   status, gate_decision, COALESCE(budget_limit_usd, expected_funds_usd, 0.0) AS budget_limit_usd,
                   COALESCE(expected_funds_usd, budget_limit_usd, 0.0) AS expected_funds_usd,
                   missing_items, expired_items, warning_items, summary_reason, created_at
            FROM `{table_id}`
            ORDER BY created_at DESC
        """
        rows = list(self._bq_client.query(query).result())
        requests: List[RoomRequestResponse] = []
        for r in rows:
            missing = json.loads(r["missing_items"]) if isinstance(r["missing_items"], str) else (r["missing_items"] or [])
            expired = json.loads(r["expired_items"]) if isinstance(r["expired_items"], str) else (r["expired_items"] or [])
            warning = json.loads(r["warning_items"]) if isinstance(r["warning_items"], str) else (r["warning_items"] or [])
            created_ts = r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"])
            requests.append(
                RoomRequestResponse(
                    request_id=r["request_id"], proposed_room_id=r["proposed_room_id"],
                    room_name=r["room_name"], institute_id=r["institute_id"],
                    requested_by=r["requested_by"], status=r["status"], gate_decision=r["gate_decision"],
                    budget_limit_usd=float(r["budget_limit_usd"] or 0.0),
                    expected_funds_usd=float(r["expected_funds_usd"] or 0.0),
                    missing_items=missing, expired_items=expired, warning_items=warning,
                    summary_reason=r["summary_reason"] or "", created_at=created_ts,
                )
            )
        return requests

    def create_room_request(self, request: CreateRoomRequest) -> RoomRequestResponse:
        """Create prospective room request, evaluate onboarding gate, and ingest to ops_room_requests."""
        req_id = request.request_id.strip()
        prop_id = "rr-" + req_id[4:] if req_id.startswith("req-") else f"rr-{req_id}"
        gate = self.evaluate_onboarding_gate(req_id)
        now_ts = datetime.now(timezone.utc).isoformat()
        doc_folder = request.document_folder_uri or f"gs://{self.settings.GCP_PROJECT_ID}-approvals/{prop_id}/"
        budget = float(request.expected_funds_usd or request.budget_limit_usd or 0.0)

        if self._bq_client:
            table_id = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_room_requests"
            rows_to_insert = [{
                "request_id": req_id, "proposed_room_id": prop_id, "room_name": request.room_name.strip(),
                "institute_id": request.institute_id.strip(), "requested_by": request.requested_by.strip(),
                "main_researcher": (request.main_researcher or request.requested_by).strip(),
                "purpose_of_research": request.purpose_of_research or "",
                "location": request.location or "Tel Aviv / Central Hub",
                "expected_funds_usd": budget, "budget_limit_usd": budget,
                "expected_time_range": request.expected_time_range or "24 months",
                "document_folder_uri": doc_folder,
                "status": "APPROVED" if gate.gate_decision == GateDecision.GATE_PASSED else "PENDING_SCAN",
                "gate_decision": gate.gate_decision.value,
                "missing_items": json.dumps(gate.missing_items),
                "expired_items": json.dumps(gate.expired_items),
                "warning_items": json.dumps(gate.warning_items),
                "summary_reason": gate.summary_reason, "scanned_at": now_ts, "created_at": now_ts,
            }]
            try:
                self._bq_client.insert_rows_json(table_id, rows_to_insert)
            except Exception as bq_err:
                logger.warning("Could not persist room request to BigQuery: %s", bq_err)

        return RoomRequestResponse(
            request_id=req_id, proposed_room_id=prop_id, room_name=request.room_name,
            institute_id=request.institute_id, requested_by=request.requested_by,
            status="APPROVED" if gate.gate_decision == GateDecision.GATE_PASSED else "PENDING_SCAN",
            gate_decision=gate.gate_decision.value, budget_limit_usd=budget,
            expected_funds_usd=budget, missing_items=gate.missing_items,
            expired_items=gate.expired_items, warning_items=gate.warning_items,
            summary_reason=gate.summary_reason, created_at=now_ts,
        )


_compliance_service_instance: Optional[ComplianceService] = None


def get_compliance_service() -> ComplianceService:
    """Return singleton instance of ComplianceService."""
    global _compliance_service_instance
    if _compliance_service_instance is None:
        _compliance_service_instance = ComplianceService()
    return _compliance_service_instance
