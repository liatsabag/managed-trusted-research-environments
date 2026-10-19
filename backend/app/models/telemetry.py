"""Telemetry, asset inventory, and operational metrics data models."""

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class QueryJobItem(BaseModel):
    """BigQuery execution job item with duration and resource telemetry."""

    job_id: str = Field(..., description="Unique BigQuery job identifier")
    room_id: Optional[str] = Field(None, description="Research Room ID associated with this query")
    project_id: str = Field(..., description="GCP Project ID where query was executed")
    user_email: Optional[str] = Field(None, description="Researcher principal email who ran the query")
    query_snippet: Optional[str] = Field(None, description="Sanitized SQL query snippet")
    bytes_billed: Optional[int] = Field(0, description="Total bytes billed for query execution")
    slot_ms: Optional[int] = Field(0, description="Total slot milliseconds consumed")
    start_time: Optional[datetime] = Field(None, description="Job execution start timestamp")
    end_time: Optional[datetime] = Field(None, description="Job execution end timestamp")
    duration_seconds: Optional[float] = Field(None, description="Total query execution duration in seconds")
    state: str = Field("DONE", description="Query execution state (e.g. DONE, RUNNING, PENDING)")
    error_message: Optional[str] = Field(None, description="Error message if query execution failed")


class AuditLogEvent(BaseModel):
    """Cloud Audit and access log event for governance telemetry."""

    event_id: str = Field(..., description="Unique audit event identifier")
    room_id: Optional[str] = Field(None, description="Associated Research Room ID")
    principal_email: str = Field(..., description="User email or service account executing action")
    service_name: str = Field("bigquery.googleapis.com", description="GCP Service Name")
    method_name: str = Field(..., description="RPC / API Method Name invoked")
    resource_name: str = Field(..., description="Full GCP resource target name")
    timestamp: datetime = Field(..., description="Audit log timestamp")
    severity: str = Field("INFO", description="Log severity level (INFO, NOTICE, WARNING, ERROR)")
    status: str = Field("SUCCESS", description="Operation status or result")
    category: Optional[str] = Field(None, description="Operational audit category")
    description: Optional[str] = Field(None, description="Deterministic human-readable description")


class DailyComputeMetricItem(BaseModel):
    """Daily grain compute, AI inference, and storage usage metrics per researcher."""

    usage_date: date = Field(..., description="Usage aggregation date")
    room_id: str = Field(..., description="Research Room ID")
    user_email: str = Field(..., description="Researcher principal email")
    institute_id: Optional[str] = Field(None, description="Institute identifier")
    query_count: int = Field(0, description="Total queries executed")
    total_bytes_billed: int = Field(0, description="Total BigQuery bytes billed")
    total_slot_hours: float = Field(0.0, description="Total BigQuery slot hours consumed")
    notebook_runtime_hours: float = Field(0.0, description="Estimated notebook runtime hours")
    ai_inference_count: int = Field(0, description="Total AI / Gemini inference invocations")
    ai_token_count: int = Field(0, description="Estimated AI / Gemini tokens consumed")
    storage_bytes: int = Field(0, description="Storage bytes in room")


class MonthlyUsageRollupItem(BaseModel):
    """Monthly rollup of compute, active researchers, and query volume per room."""

    usage_month: date = Field(..., description="Usage month start date")
    room_id: str = Field(..., description="Research Room ID")
    institute_id: str = Field(..., description="Institute identifier")
    avg_active_researchers: float = Field(0.0, description="Average active researchers")
    total_notebook_hours: float = Field(0.0, description="Total notebook session hours")
    total_query_volume_tb: float = Field(0.0, description="Total query volume in TB")
    total_slot_hours: float = Field(0.0, description="Total slot hours")


class NotebookSessionItem(BaseModel):
    """Persisted daily notebook and compute session active runtime per researcher."""

    room_id: str = Field(..., description="Research Room ID")
    user_email: str = Field(..., description="Researcher principal email")
    session_date: date = Field(..., description="Session date")
    notebook_name: Optional[str] = Field(None, description="Colab Enterprise or Jupyter notebook name")
    runtime_id: Optional[str] = Field(None, description="Colab Enterprise runtime ID")
    machine_type: Optional[str] = Field(None, description="Compute engine machine type e.g. e2-standard-4")
    runtime_template_id: Optional[str] = Field(None, description="Colab runtime template identifier")
    total_events: int = Field(0, description="Total compute events count")
    session_starts: int = Field(0, description="Session start events count")
    session_stops: int = Field(0, description="Session stop events count")
    total_sessions: int = Field(1, description="Estimated total sessions")
    total_active_hours: float = Field(0.0, description="Estimated active runtime hours")
    first_session_start: Optional[datetime] = Field(None, description="First session timestamp")
    last_session_end: Optional[datetime] = Field(None, description="Last session timestamp")


class AIUsageMetricItem(BaseModel):
    """Persisted daily AI and Gemini inference invocation counts per researcher."""

    room_id: str = Field(..., description="Research Room ID")
    project_id: str = Field(..., description="GCP Project ID")
    user_email: str = Field(..., description="Researcher principal email")
    usage_date: date = Field(..., description="Usage date")
    service_name: str = Field(..., description="AI service name")
    total_inference_calls: int = Field(0, description="Total inference invocations")
    successful_calls: int = Field(0, description="Successful inference calls")
    failed_calls: int = Field(0, description="Failed inference calls")
    first_invoked_at: Optional[datetime] = Field(None, description="First invocation timestamp")
    last_invoked_at: Optional[datetime] = Field(None, description="Last invocation timestamp")


class TelemetrySyncResponse(BaseModel):
    """Status response for telemetry synchronization procedures."""

    status: str = Field("SUCCESS", description="Sync status")
    sync_timestamp: datetime = Field(..., description="Timestamp of sync execution")
    message: str = Field(..., description="Status summary message")


class RoomAssetInventory(BaseModel):
    """Asset, table, storage, and notebook inventory breakdown for a Research Room."""

    room_id: str = Field(..., description="Research Room identifier")
    local_tables_count: int = Field(0, description="Number of spoke-local BigQuery tables")
    shared_tables_count: int = Field(0, description="Number of linked shared BigQuery tables")
    total_accessible_tables: int = Field(0, description="Total accessible BigQuery tables in room")
    inbound_bytes: int = Field(0, description="Total size in bytes of inbound storage bucket")
    inbound_objects: int = Field(0, description="Total object count in inbound storage bucket")
    export_bytes: int = Field(0, description="Total size in bytes of export storage bucket")
    export_objects: int = Field(0, description="Total object count in export storage bucket")
    notebooks_count: int = Field(0, description="Total count of Jupyter notebooks (.ipynb) in room")


class FleetTelemetryOverview(BaseModel):
    """Fleet-wide aggregated activity and storage telemetry metrics."""

    active_researchers_24h: int = Field(0, description="Unique active researchers in last 24 hours")
    active_researchers_7d: int = Field(0, description="Unique active researchers in last 7 days")
    active_researchers_30d: int = Field(0, description="Unique active researchers in last 30 days")
    total_queries_24h: int = Field(0, description="Total queries executed across fleet in last 24 hours")
    total_bytes_scanned_30d: int = Field(0, description="Total bytes scanned across fleet in last 30 days")
    total_fleet_storage_bytes: int = Field(0, description="Total storage bytes across all room buckets")


class RoomActivitySummary(BaseModel):
    """Room activity summary with recent queries, audit logs, and last active session."""

    room_id: str = Field(..., description="Research Room identifier")
    recent_queries: List[QueryJobItem] = Field(default_factory=list, description="Recent queries executed in room")
    recent_audit_events: List[AuditLogEvent] = Field(default_factory=list, description="Recent audit log events in room")
    last_active_session: Optional[datetime] = Field(None, description="Timestamp of most recent activity in room")
    total_queries_count: int = Field(0, description="Total BigQuery queries executed in room")
    researcher_queries_count: int = Field(0, description="Total queries executed exclusively by researchers")
    total_notebook_runs: int = Field(0, description="Total notebook execution sessions by researchers")
    total_notebook_hours: float = Field(0.0, description="Total active notebook runtime hours by researchers")
    active_researcher_email: Optional[str] = Field(None, description="Email of most recently active researcher")
    active_researcher_name: Optional[str] = Field(None, description="Display name of most recently active researcher")
