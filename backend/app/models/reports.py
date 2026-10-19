"""Pydantic models for Standardized & Ad-Hoc Governance Reports Engine."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    """Metadata describing a generated compliance or fleet report."""
    report_id: str = Field(..., description="Unique generated report identifier")
    report_type: str = Field(..., description="Report type code")
    title: str = Field(..., description="Human-readable report title")
    description: str = Field(..., description="Detailed description of contents")
    generated_at: str = Field(..., description="ISO 8601 generation timestamp")
    generated_by: str = Field("Central Administrator Portal", description="Generator identity")
    record_count: int = Field(0, description="Number of items in the report dataset")
    supported_formats: List[str] = Field(default_factory=lambda: ["json", "csv", "pdf"])


class FleetInventoryReportItem(BaseModel):
    """Row item in Room Fleet Inventory Report."""
    room_id: str
    room_name: str
    institute_id: str
    institute_name: str
    spoke_project_id: str
    status: str
    budget_limit_usd: float
    active_researchers_count: int
    created_at: str
    packages_count: int = 0
    inbound_bucket: Optional[str] = None
    export_bucket: Optional[str] = None


class ComplianceExceptionReportItem(BaseModel):
    """Row item in Compliance Exceptions Report."""
    room_id: str
    room_name: str
    institute_id: str
    missing_items: List[str]
    missing_count: int
    gate_decision: str
    status: str
    severity: str
    last_evaluated_at: str


class ApprovalExpirationHorizonItem(BaseModel):
    """Row item in Approval Expirations Horizon Report."""
    room_id: str
    room_name: str
    institute_id: str
    document_type: str
    expiration_date: str
    days_remaining: int
    urgency_tier: str
    action_required: str


class CostFinOpsReportItem(BaseModel):
    """Row item in Cost & FinOps Resource Billing Report."""
    room_id: str
    room_name: str
    institute_id: str
    institute_name: str
    budget_limit_usd: float
    actual_spend_usd: float
    budget_utilization_pct: float
    storage_spend_usd: float
    compute_spend_usd: float
    bigquery_spend_usd: float
    ai_spend_usd: float
    burn_rate_daily_usd: float


class EgressAuditReportItem(BaseModel):
    """Row item in Airlock Egress Inspection Audit Report."""
    scan_id: Optional[str]
    room_id: str
    file_name: str
    bucket_name: str
    file_size_bytes: int
    researcher_email: Optional[str] = ""
    status: str
    risk_score: Optional[int]
    risk_level: Optional[str]
    pii_tokens_count: int
    k_anonymity_violation: bool
    decision: str
    scanned_at: Optional[str]


class ReportGenerationResponse(BaseModel):
    """Unified response envelope containing report metadata and tabular records."""
    metadata: ReportMetadata
    records: List[Dict[str, Any]]
    csv_download_url: Optional[str] = None
    json_download_url: Optional[str] = None
