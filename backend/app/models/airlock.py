"""Pydantic data models for Airlock Egress Governance and Gemini Risk Scanner."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AirlockExportCandidate(BaseModel):
    """Candidate analytical file staged in spoke egress bucket awaiting airlock clearance."""

    scan_id: Optional[str] = Field(None, description="Unique scan identifier")
    room_id: str = Field(..., description="Research room identifier")
    file_name: str = Field(..., description="Candidate file name in export bucket")
    bucket_name: str = Field(..., description="GCS spoke export bucket name")
    file_size_bytes: int = Field(0, description="File size in bytes")
    created_at: Optional[str] = Field(None, description="ISO upload timestamp")
    researcher_email: Optional[str] = Field(None, description="Authoring researcher identity")
    status: str = Field("PENDING_SCAN", description="Egress state: PENDING_SCAN, SCANNED, APPROVED, REJECTED, FLAGGED")
    risk_score: Optional[int] = Field(None, description="Gemini privacy risk score 0-100")
    risk_level: Optional[str] = Field(None, description="Risk level: LOW, MEDIUM, HIGH, CRITICAL")
    pii_tokens_detected: List[str] = Field(default_factory=list, description="Detected PII / direct identifier tokens")
    k_anonymity_violation: bool = Field(False, description="True if cell count or k-anonymity k < 5 is violated")
    findings: List[str] = Field(default_factory=list, description="Detailed HIPAA / privacy audit findings")
    recommendation: Optional[str] = Field(None, description="Gemini policy recommendation: APPROVE, FLAG_FOR_REVIEW, REJECT")
    reason: Optional[str] = Field(None, description="Synthesized safety rationale")
    scanned_at: Optional[str] = Field(None, description="ISO timestamp of last Gemini AI scan")


class AirlockScanRequest(BaseModel):
    """Payload to trigger an on-demand Gemini privacy scan on candidate files."""

    room_id: str = Field(..., description="Target research room ID")
    file_name: Optional[str] = Field(None, description="Optional specific file name; if None, scans all pending files")


class AirlockActionRequest(BaseModel):
    """Payload to approve or reject an egress export candidate."""

    room_id: str = Field(..., description="Target research room ID")
    file_name: str = Field(..., description="Target file name")
    action: str = Field(..., description="Decision action: APPROVE or REJECT")
    comment: Optional[str] = Field(None, description="Optional administrative rationale")


class AirlockActionResponse(BaseModel):
    """Response confirming egress action."""

    room_id: str
    file_name: str
    action: str
    status: str
    message: str
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
