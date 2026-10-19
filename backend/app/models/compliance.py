"""Pydantic data models for 5-Item Regulatory Checklist and Gemini Governance."""

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RegulatoryItemType(str, Enum):
    """Statutory 5-Item prerequisite types."""
    RESEARCH_PROTOCOL = "Research_Protocol"
    HELSINKI_IRB = "Helsinki_IRB"
    DATA_TRANSFER = "Data_Transfer"
    EXTRACTION_PROTOCOL = "Extraction_Protocol"
    DUA = "DUA"


class RegulatoryItemStatus(str, Enum):
    """Lifecycle status for a regulatory checklist item."""
    APPROVED = "Approved"
    EXPIRED = "Expired"
    PENDING_REVIEW = "Pending_Review"
    MISSING = "Missing"
    REJECTED = "Rejected"


class GateDecision(str, Enum):
    """Decision outcome for pre-flight onboarding gate scans."""
    GATE_PASSED = "GATE_PASSED"
    GATE_WARNING = "GATE_WARNING"
    GATE_BLOCKED = "GATE_BLOCKED"


class RoomOverallCompliance(str, Enum):
    """Aggregate compliance status for active research rooms."""
    COMPLIANT = "COMPLIANT"
    EXPIRING_SOON = "EXPIRING_SOON"
    NON_COMPLIANT = "NON_COMPLIANT"
    INCOMPLETE = "INCOMPLETE"


class RegulatoryChecklistItem(BaseModel):
    """Detailed metadata for a single regulatory approval item."""
    item_id: str = Field(..., description="Unique ID: <room_id>-<item_type>")
    room_id: str = Field(..., description="Associated research room ID or request ID")
    room_type: str = Field(default="PROVISIONED", description="'PROVISIONED' or 'PENDING_REQUEST'")
    item_type: RegulatoryItemType = Field(..., description="Regulatory category")
    item_name: str = Field(..., description="Human-readable title")
    status: RegulatoryItemStatus = Field(default=RegulatoryItemStatus.MISSING)
    approval_date: Optional[str] = Field(None, description="ISO approval date")
    expiration_date: Optional[str] = Field(None, description="ISO expiration date")
    approver_name: Optional[str] = Field(None, description="Signatory authority")
    document_uri: Optional[str] = Field(None, description="GCS URI to document")
    comments: Optional[str] = Field(None, description="Audit or parsing rationale")
    days_remaining: Optional[int] = Field(None, description="Days until expiration")
    is_valid: bool = Field(default=False, description="True if Approved and days > 0")


class RoomComplianceSummary(BaseModel):
    """Aggregated compliance view for an active research room."""
    room_id: str
    room_name: Optional[str] = None
    overall_status: RoomOverallCompliance = RoomOverallCompliance.INCOMPLETE
    items: Dict[str, RegulatoryChecklistItem] = Field(default_factory=dict)
    min_days_remaining: Optional[int] = None
    iam_state: str = "ACTIVE"
    last_scanned_at: Optional[str] = None


class OnboardingGateRequest(BaseModel):
    """Request payload for pre-flight onboarding gate evaluation."""
    request_id: str
    proposed_room_id: Optional[str] = None
    document_bucket_uri: Optional[str] = None


class OnboardingGateResponse(BaseModel):
    """Response payload with pre-flight onboarding evaluation results."""
    request_id: str
    gate_decision: GateDecision
    items: Dict[str, RegulatoryChecklistItem] = Field(default_factory=dict)
    missing_items: List[str] = Field(default_factory=list)
    expired_items: List[str] = Field(default_factory=list)
    warning_items: List[str] = Field(default_factory=list)
    summary_reason: str
    evaluated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ComplianceHorizonReport(BaseModel):
    """Fleet-wide compliance horizon expiration forecast."""
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    expiring_30_days: List[RegulatoryChecklistItem] = Field(default_factory=list)
    expiring_60_days: List[RegulatoryChecklistItem] = Field(default_factory=list)
    expiring_90_days: List[RegulatoryChecklistItem] = Field(default_factory=list)
    non_compliant_rooms: List[str] = Field(default_factory=list)


class ComplianceScanResult(BaseModel):
    """Summary result returned after triggering an on-demand room compliance scan."""
    room_id: str
    scanned_documents_count: int = 0
    items: Dict[str, RegulatoryChecklistItem] = Field(default_factory=dict)
    action_taken: Optional[str] = None
    previous_iam_state: Optional[str] = None
    new_iam_state: Optional[str] = None
    message: str


class CreateRoomRequest(BaseModel):
    """Payload for submitting a prospective Research Room request."""
    request_id: str = Field(..., description="Unique request ID, e.g. 'req-neuro-05'")
    room_name: str = Field(..., description="Human-readable room title")
    institute_id: str = Field(..., description="Associated medical institute ID")
    requested_by: str = Field(..., description="Primary requester name or email")
    main_researcher: Optional[str] = Field(None, description="Lead investigator")
    purpose_of_research: Optional[str] = Field(None, description="Research hypothesis and scope")
    location: Optional[str] = Field("Tel Aviv / Central Hub", description="Physical or logical region")
    expected_funds_usd: Optional[float] = Field(0.0, description="Allocated grant or project budget")
    budget_limit_usd: Optional[float] = Field(0.0, description="Allocated grant or project budget")
    expected_time_range: Optional[str] = Field("24 months", description="Estimated study duration")
    document_folder_uri: Optional[str] = Field(None, description="GCS bucket directory containing approval PDFs")


class RoomRequestResponse(BaseModel):
    """Response returned upon ingesting and evaluating a prospective room request."""
    request_id: str
    proposed_room_id: str
    room_name: str
    institute_id: str
    requested_by: str
    status: str
    gate_decision: str
    budget_limit_usd: Optional[float] = 0.0
    expected_funds_usd: Optional[float] = 0.0
    missing_items: List[str] = Field(default_factory=list)
    expired_items: List[str] = Field(default_factory=list)
    warning_items: List[str] = Field(default_factory=list)
    summary_reason: str
    created_at: str
