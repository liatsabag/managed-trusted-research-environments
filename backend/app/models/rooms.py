"""Pydantic data models for Research Rooms, Fleet Registry, and Governance."""

from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResearcherMember(BaseModel):
    """Researcher member belonging to a research room."""

    researcher_id: str = Field(..., description="Unique researcher identifier")
    first_name: str = Field(..., description="Researcher first name")
    last_name: str = Field(..., description="Researcher last name")
    primary_email: str = Field(..., description="Primary institutional email")
    role: str = Field(..., description="Researcher role (e.g., PI, Specialist)")
    access_state: str = Field("ACTIVE", description="IAM access state (ACTIVE, DOWNGRADED_READONLY, SUSPENDED)")
    org_unit_path: Optional[str] = Field(None, description="Cloud Identity Org Unit path")
    is_active: bool = Field(True, description="Whether researcher account is active")
    institute_id: Optional[str] = Field(None, description="Affiliated institute ID")
    room_id: Optional[str] = Field(None, description="Assigned research room ID")
    last_activity_at: Optional[str] = Field(None, description="Last activity timestamp in ISO format")


class RoomPackageItem(BaseModel):
    """Software package or library installed in a research room runtime."""

    room_id: str = Field(..., description="Associated research room ID")
    runtime_id: Optional[str] = Field(None, description="Runtime template identifier")
    package_name: str = Field(..., description="Name of the software package")
    package_version: str = Field(..., description="Version of the package")
    package_type: str = Field("python_package", description="Package category (e.g. python_package, tool)")
    installed_at: Optional[str] = Field(None, description="Installation timestamp")


class DUAComplianceStatus(BaseModel):
    """Helsinki Ethics and Data Use Agreement compliance metrics."""

    helsinki_expiry_date: Optional[str] = Field(None, description="Helsinki IRB expiration date (YYYY-MM-DD)")
    dua_expiry_date: Optional[str] = Field(None, description="Data Use Agreement expiration date (YYYY-MM-DD)")
    helsinki_days_remaining: Optional[int] = Field(None, description="Days until Helsinki IRB expiration")
    dua_days_remaining: Optional[int] = Field(None, description="Days until DUA expiration")
    is_helsinki_valid: bool = Field(True, description="True if Helsinki IRB approval is currently valid")
    is_dua_valid: bool = Field(True, description="True if Data Use Agreement is currently valid")
    compliance_level: str = Field("COMPLIANT", description="Overall status: COMPLIANT, WARNING, EXPIRED, NON_COMPLIANT")
    requires_action: bool = Field(False, description="True if immediate administrative review is required")
    notes: Optional[str] = Field(None, description="Compliance status comments or warning details")


class ResearchRoomSummary(BaseModel):
    """Summary representation of a Research Room for fleet listings."""

    room_id: str = Field(..., description="Unique research room ID")
    room_name: str = Field(..., description="Human-readable room name")
    institute_id: str = Field(..., description="Affiliated partner institute ID")
    institute_name: Optional[str] = Field(None, description="Name of the partner institute")
    lead_researcher_id: Optional[str] = Field(None, description="Lead researcher ID")
    lead_researcher: Optional[str] = Field(None, description="Lead researcher or Principal Investigator name")
    lead_researcher_email: Optional[str] = Field(None, description="Lead researcher email")
    deployment_date: Optional[str] = Field(None, description="Room deployment date (YYYY-MM-DD)")
    spoke_project_id: str = Field(..., description="GCP Spoke Project ID")
    status: str = Field("ACTIVE", description="Room operational status (ACTIVE, SOFT_DOWNGRADED, ARCHIVED)")
    compliance: DUAComplianceStatus = Field(..., description="DUA & Helsinki compliance details")
    researcher_count: int = Field(0, description="Total active researchers assigned")
    table_count: int = Field(0, description="Number of local tables in spoke dataset")
    packages_count: int = Field(0, description="Total installed analytical packages")
    active_packages: List[str] = Field(default_factory=list, description="Top installed package names")
    total_cost: float = Field(0.0, description="Total invoiced spend since deployment (USD)")
    budget_limit_usd: float = Field(5000.0, description="Allocated financial budget limit (USD)")
    last_activity_at: Optional[str] = Field(None, description="Timestamp of most recent activity in this room")
    health_status: str = Field("HEALTHY", description="Infrastructure health status: HEALTHY, DEGRADED, DOWNGRADED")


class ResearchRoomDetail(BaseModel):
    """Comprehensive detail representation of a single Research Room."""

    room_id: str = Field(..., description="Unique research room ID")
    room_name: str = Field(..., description="Human-readable room name")
    institute_id: str = Field(..., description="Affiliated partner institute ID")
    institute_name: Optional[str] = Field(None, description="Name of the partner institute")
    lead_researcher_id: Optional[str] = Field(None, description="Lead researcher ID")
    lead_researcher: Optional[str] = Field(None, description="Lead researcher or Principal Investigator name")
    lead_researcher_email: Optional[str] = Field(None, description="Lead researcher email")
    deployment_date: Optional[str] = Field(None, description="Room deployment date (YYYY-MM-DD)")
    spoke_project_id: str = Field(..., description="GCP Spoke Project ID")
    status: str = Field("ACTIVE", description="Room operational status (ACTIVE, SOFT_DOWNGRADED, ARCHIVED)")
    compliance: DUAComplianceStatus = Field(..., description="DUA & Helsinki compliance details")
    budget_limit_usd: float = Field(5000.0, description="Allocated financial budget limit (USD)")
    total_cost: float = Field(0.0, description="Total invoiced spend since deployment (USD)")
    inbound_bucket: str = Field(..., description="GCS Inbound bucket URI")
    export_bucket: str = Field(..., description="GCS Export/Airlock bucket URI")
    cloud_identity_group: str = Field(..., description="Cloud Identity IAM group email")
    vpc_name: Optional[str] = Field(None, description="Dedicated Spoke VPC network name")
    subnet_name: Optional[str] = Field(None, description="Dedicated Spoke subnetwork name")
    template_id: Optional[str] = Field(None, description="Colab Enterprise Runtime Template ID")
    template_name: Optional[str] = Field(None, description="Display name of Runtime Template")
    shared_dataset_subscriptions: List[str] = Field(default_factory=list, description="Subscribed Hub datasets")
    local_dataset_id: Optional[str] = Field(None, description="Spoke local dataset ID")
    tables_count: int = Field(0, description="Number of spoke tables")
    researchers: List[ResearcherMember] = Field(default_factory=list, description="Assigned researchers roster")
    packages: List[RoomPackageItem] = Field(default_factory=list, description="Installed software packages")
    health_status: str = Field("HEALTHY", description="Infrastructure health status: HEALTHY, DEGRADED, DOWNGRADED")
    health_details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detailed health checks")


class InstituteSummary(BaseModel):
    """Partner research institute summary and room associations."""

    institute_id: str = Field(..., description="Unique institute identifier")
    name: str = Field(..., description="Official institute name")
    contact_email: str = Field(..., description="Compliance and administrative contact email")
    country: str = Field("USA", description="ISO country code")
    room_count: int = Field(0, description="Number of affiliated research rooms")
    rooms: List[str] = Field(default_factory=list, description="List of affiliated room IDs")


class DowngradeRequest(BaseModel):
    """Payload for requesting IAM soft-downgrade on a research room."""

    reason: Optional[str] = Field("Compliance enforcement: Helsinki/DUA expiration", description="Downgrade reason")
    target_role: Optional[str] = Field("roles/viewer", description="Restricted reader IAM role")
    notify_researchers: bool = Field(True, description="Whether to trigger notification to researchers")


class RoomActionResponse(BaseModel):
    """Response payload for administrative room lifecycle operations."""

    room_id: str = Field(..., description="Target research room ID")
    action: str = Field(..., description="Executed action: downgrade, reactivate, update_status")
    previous_status: str = Field(..., description="Status before action execution")
    new_status: str = Field(..., description="Status after action execution")
    affected_researchers: List[str] = Field(default_factory=list, description="List of updated researcher emails")
    success: bool = Field(True, description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result summary")
    timestamp: str = Field(..., description="Action execution ISO timestamp")


class StatusUpdateRequest(BaseModel):
    """Payload for updating research room status (ACTIVE, SOFT_DOWNGRADED, SUSPENDED)."""

    new_status: str = Field(..., description="Target status: ACTIVE, SOFT_DOWNGRADED, SUSPENDED")
    reason: Optional[str] = Field("Administrative policy update", description="Reason for status change")


class AddResearcherRequest(BaseModel):
    """Payload for provisioning a researcher stub to a research room."""

    researcher_email: str = Field(..., description="Institutional email of researcher")
    role: Optional[str] = Field("Researcher", description="Assigned role")


class AddResearcherResponse(BaseModel):
    """Response payload for adding a researcher stub."""

    room_id: str = Field(..., description="Target research room ID")
    researcher_email: str = Field(..., description="Provisioned researcher email")
    role: str = Field("Researcher", description="Researcher role")
    status: str = Field("PROVISIONED_STUB", description="Provisioning status")
    message: str = Field(..., description="Status message")
    timestamp: str = Field(..., description="Action timestamp")

