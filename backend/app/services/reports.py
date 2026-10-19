"""Standardized and Ad-Hoc Governance Reports Generation Service."""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import bigquery

from backend.app.core.config import get_settings
from backend.app.models.reports import (
    ApprovalExpirationHorizonItem,
    ComplianceExceptionReportItem,
    CostFinOpsReportItem,
    EgressAuditReportItem,
    FleetInventoryReportItem,
    ReportGenerationResponse,
    ReportMetadata,
)

logger = logging.getLogger("reports_service")


class ReportsService:
    """Generates standardized and ad-hoc governance reports in CSV, PDF/HTML, and JSON."""

    def __init__(self, bq_client: Optional[bigquery.Client] = None):
        settings = get_settings()
        self.hub_project = getattr(settings, "GCP_PROJECT_ID", "gcp-rr-hub-core")
        self.telemetry_dataset = getattr(settings, "HUB_TELEMETRY_DATASET", "hub_telemetry")
        self.registry_dataset = getattr(settings, "HUB_REGISTRY_DATASET", "hub_registry")
        self.client = bq_client or bigquery.Client(project=self.hub_project)

    def get_fleet_inventory_report(self) -> ReportGenerationResponse:
        """Report 1: Room Fleet Inventory - Complete status & configuration."""
        q = f"""
        SELECT r.room_id, r.room_name, r.institute_id, i.name AS institute_name,
               r.spoke_project_id, r.status, IFNULL(r.budget_limit_usd, 5000.0) AS budget_limit_usd,
               r.created_at, r.inbound_bucket, r.export_bucket,
               (SELECT COUNT(1) FROM `{self.hub_project}.{self.registry_dataset}.reg_researchers` u WHERE u.room_id = r.room_id AND u.is_active = TRUE) AS active_researchers_count,
               (SELECT COUNT(1) FROM `{self.hub_project}.{self.registry_dataset}.reg_room_packages` p WHERE p.room_id = r.room_id) AS packages_count
        FROM `{self.hub_project}.{self.registry_dataset}.reg_research_rooms` r
        LEFT JOIN `{self.hub_project}.{self.registry_dataset}.reg_institutes` i ON r.institute_id = i.institute_id
        ORDER BY r.room_id ASC
        """
        rows = [dict(r) for r in self.client.query(q).result()]
        records = [
            FleetInventoryReportItem(
                room_id=row["room_id"], room_name=row["room_name"],
                institute_id=row.get("institute_id", ""), institute_name=row.get("institute_name") or row.get("institute_id", ""),
                spoke_project_id=row.get("spoke_project_id", ""), status=row.get("status", "ACTIVE"),
                budget_limit_usd=float(row.get("budget_limit_usd") or 5000.0),
                active_researchers_count=int(row.get("active_researchers_count") or 0),
                created_at=str(row.get("created_at") or datetime.now(timezone.utc).isoformat()),
                packages_count=int(row.get("packages_count") or 0),
                inbound_bucket=row.get("inbound_bucket_name"), export_bucket=row.get("export_bucket_name"),
            ).dict() for row in rows
        ]
        meta = ReportMetadata(
            report_id=f"rep-fleet-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            report_type="FLEET_INVENTORY", title="Room Fleet Inventory Report",
            description="Complete operational status, cloud spoke mapping, grant budget, and package configuration across research rooms.",
            generated_at=datetime.now(timezone.utc).isoformat(), record_count=len(records),
        )
        return ReportGenerationResponse(metadata=meta, records=records)

    def get_compliance_exceptions_report(self) -> ReportGenerationResponse:
        """Report 2: Compliance Exceptions Report - Flagged studies with missing/incomplete items."""
        q = f"""
        SELECT c.room_id, r.room_name, r.institute_id,
               ARRAY_AGG(c.item_type ORDER BY c.item_type) AS missing_items,
               COUNT(c.item_type) AS missing_count,
               'GATE_BLOCKED' AS gate_decision,
               r.status,
               MAX(c.last_updated) AS last_evaluated_at
        FROM `{self.hub_project}.{self.telemetry_dataset}.ops_regulatory_checklist` c
        LEFT JOIN `{self.hub_project}.{self.registry_dataset}.reg_research_rooms` r ON c.room_id = r.room_id
        WHERE c.status IN ('MISSING', 'EXPIRED', 'PENDING_APPROVAL')
        GROUP BY c.room_id, r.room_name, r.institute_id, r.status
        """
        rows = [dict(r) for r in self.client.query(q).result()]
        records = [
            ComplianceExceptionReportItem(
                room_id=row["room_id"], room_name=row.get("room_name") or row["room_id"],
                institute_id=row.get("institute_id") or "UNKNOWN",
                missing_items=list(row.get("missing_items") or []),
                missing_count=int(row.get("missing_count") or len(row.get("missing_items") or [])),
                gate_decision=row.get("gate_decision", "GATE_BLOCKED"),
                status=row.get("status") or "ACTIVE",
                severity="CRITICAL" if len(row.get("missing_items") or []) >= 2 else "WARNING",
                last_evaluated_at=str(row.get("last_evaluated_at") or datetime.now(timezone.utc).isoformat()),
            ).dict() for row in rows
        ]
        meta = ReportMetadata(
            report_id=f"rep-comp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            report_type="COMPLIANCE_EXCEPTIONS", title="Compliance & Gate Exceptions Report",
            description="Audit report of research environments with missing, lapsed, or unapproved statutory compliance prerequisites.",
            generated_at=datetime.now(timezone.utc).isoformat(), record_count=len(records),
        )
        return ReportGenerationResponse(metadata=meta, records=records)

    def get_approval_expirations_report(self) -> ReportGenerationResponse:
        """Report 3: Approval Expirations Horizon - Proactive report of ethics/Helsinki certificates expiring."""
        q = f"""
        SELECT c.room_id, r.room_name, r.institute_id, c.item_type AS document_type,
               c.expiration_date,
               DATE_DIFF(c.expiration_date, CURRENT_DATE(), DAY) AS days_remaining
        FROM `{self.hub_project}.{self.telemetry_dataset}.ops_regulatory_checklist` c
        LEFT JOIN `{self.hub_project}.{self.registry_dataset}.reg_research_rooms` r ON c.room_id = r.room_id
        WHERE c.expiration_date IS NOT NULL
        ORDER BY c.expiration_date ASC
        """
        rows = [dict(r) for r in self.client.query(q).result()]
        records = []
        for row in rows:
            days = int(row.get("days_remaining") or 0)
            urgency = "URGENT" if days <= 30 else ("WARNING" if days <= 60 else "MONITORED")
            action = "Immediate IRB renewal required" if days <= 30 else ("Submit annual extension dossier" if days <= 60 else "Routine review")
            records.append(ApprovalExpirationHorizonItem(
                room_id=row["room_id"], room_name=row.get("room_name") or row["room_id"],
                institute_id=row.get("institute_id") or "UNKNOWN",
                document_type=row.get("document_type", "IRB_Approval"),
                expiration_date=str(row.get("expiration_date")),
                days_remaining=days, urgency_tier=urgency, action_required=action,
            ).dict())

        meta = ReportMetadata(
            report_id=f"rep-horizon-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            report_type="APPROVAL_HORIZON", title="Ethics & Helsinki Approval Expiration Horizon",
            description="Proactive forward-looking forecast of institutional regulatory certificates and DUA agreements expiring in 30/60/90 days.",
            generated_at=datetime.now(timezone.utc).isoformat(), record_count=len(records),
        )
        return ReportGenerationResponse(metadata=meta, records=records)

    def get_cost_finops_report(self) -> ReportGenerationResponse:
        """Report 4: Cost & FinOps Report - Segmented by room, institute, grant budget & cost drivers."""
        from backend.app.services.finops import get_finops_service
        finops_service = get_finops_service()
        summary = finops_service.get_summary()

        records = []
        for r in summary.rooms:
            b_limit = float(r.budget_limit_usd or 5000.0)
            tot_spend = round(r.total_invoiced_cost, 2)
            util_pct = round((tot_spend / b_limit) * 100, 2) if b_limit > 0 else 0.0
            daily_burn = round(tot_spend / 30.0, 2)
            cd = r.cost_drivers
            records.append(CostFinOpsReportItem(
                room_id=r.room_id,
                room_name=r.room_name,
                institute_id=r.institute_id or "",
                institute_name=r.institute_id or "",
                budget_limit_usd=b_limit,
                actual_spend_usd=tot_spend,
                budget_utilization_pct=util_pct,
                storage_spend_usd=round(cd.storage_cost, 2),
                compute_spend_usd=round(cd.compute_notebooks_cost, 2),
                bigquery_spend_usd=round(cd.bigquery_cost, 2),
                ai_spend_usd=round(cd.vertex_ai_cost, 2),
                burn_rate_daily_usd=daily_burn,
            ).dict())

        meta = ReportMetadata(
            report_id=f"rep-finops-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            report_type="FINOPS_BILLING",
            title="Cost & FinOps Resource Billing Report",
            description="Multi-tenant cloud expenditure breakdown segmented by room, institute, grant budget ceiling, and cost drivers.",
            generated_at=datetime.now(timezone.utc).isoformat(),
            record_count=len(records),
        )
        return ReportGenerationResponse(metadata=meta, records=records)

    def get_egress_audit_report(self) -> ReportGenerationResponse:
        """Report 5: Egress Audit Report - Historical log of all file export requests, inspection outcomes & risk decisions."""
        q = f"""
        SELECT scan_id, room_id, file_name, bucket_name, file_size_bytes,
               researcher_email, status, risk_score, risk_level,
               ARRAY_LENGTH(pii_tokens) AS pii_tokens_count,
               k_anonymity_violation, IFNULL(recommendation, 'APPROVED') AS decision, scanned_at
        FROM `{self.hub_project}.{self.telemetry_dataset}.ops_airlock_export_scans`
        ORDER BY scanned_at DESC
        LIMIT 100
        """
        rows = [dict(r) for r in self.client.query(q).result()]
        records = [
            EgressAuditReportItem(
                scan_id=row.get("scan_id"), room_id=row["room_id"],
                file_name=row.get("file_name", ""), bucket_name=row.get("bucket_name", ""),
                file_size_bytes=int(row.get("file_size_bytes") or 0),
                researcher_email=row.get("researcher_email") or "",
                status=row.get("status", "COMPLETED"),
                risk_score=row.get("risk_score"),
                risk_level=row.get("risk_level"),
                pii_tokens_count=int(row.get("pii_tokens_count") or 0),
                k_anonymity_violation=bool(row.get("k_anonymity_violation")),
                decision=row.get("decision") or "APPROVED",
                scanned_at=str(row.get("scanned_at")) if row.get("scanned_at") else None,
            ).dict() for row in rows
        ]
        meta = ReportMetadata(
            report_id=f"rep-egress-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            report_type="EGRESS_AUDIT", title="Airlock Data Egress & AI Risk Inspection Audit Log",
            description="Forensic record of all egress candidate scans, detected PII tokens, k-anonymity violations, and gate decisions.",
            generated_at=datetime.now(timezone.utc).isoformat(), record_count=len(records),
        )
        return ReportGenerationResponse(metadata=meta, records=records)

    def export_as_csv(self, report_response: ReportGenerationResponse) -> str:
        """Serializes report tabular records into standard CSV format."""
        if not report_response.records:
            return ""
        output = io.StringIO()
        fieldnames = list(report_response.records[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in report_response.records:
            # Flatten lists if present
            row = {}
            for k, v in r.items():
                if isinstance(v, list):
                    row[k] = "; ".join(str(item) for item in v)
                else:
                    row[k] = v
            writer.writerow(row)
        return output.getvalue()


_reports_service_instance: Optional[ReportsService] = None


def get_reports_service() -> ReportsService:
    global _reports_service_instance
    if _reports_service_instance is None:
        _reports_service_instance = ReportsService()
    return _reports_service_instance
