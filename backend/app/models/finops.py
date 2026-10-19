"""Pydantic models for FinOps Hierarchical SKU, Capacity, and Telemetry Attribution Engine."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SKUBillingItem(BaseModel):
    """Billed line item from GCP Billing Export."""
    sku_id: Optional[str] = Field(None, description="GCP SKU identifier")
    sku_description: str = Field(..., description="SKU description (e.g. Analysis, Predefined Core)")
    service_description: str = Field(..., description="Service display name (e.g. BigQuery, Compute Engine)")
    usage_amount: Optional[float] = Field(0.0, description="Raw usage quantity from billing export")
    usage_unit: Optional[str] = Field(None, description="Usage unit (e.g. tib, hours, gib-months)")
    cost: float = Field(0.0, description="Billed line item cost in USD")
    currency: str = Field("USD", description="Currency code (USD)")


class ResearcherTelemetryUsage(BaseModel):
    """Fine-grained actor compute, AI, and storage telemetry usage."""
    total_bytes_billed: int = Field(0, description="BigQuery query bytes billed")
    query_count: int = Field(0, description="Total SQL query execution count")
    notebook_runtime_hours: float = Field(0.0, description="Vertex/Colab notebook runtime hours")
    ai_token_count: int = Field(0, description="Vertex AI generative token usage")
    storage_bytes: int = Field(0, description="Cloud Storage bytes maintained")


class ResearcherSKUAttribution(BaseModel):
    """Cost attribution and formula weight for an individual SKU."""
    sku_id: Optional[str] = Field(None, description="GCP SKU identifier")
    sku_description: str = Field(..., description="SKU display description")
    weight: float = Field(0.0, description="Proportional weight W(actor, SKU) between 0.0 and 1.0")
    formula_applied: str = Field(..., description="Mathematical formula expression applied for attribution")
    allocated_cost: float = Field(0.0, description="Cost apportioned to this actor for the SKU")


class ResearcherCostDetail(BaseModel):
    """Hierarchical cost attribution and telemetry usage for a registered researcher."""
    researcher_id: str = Field(..., description="Unique researcher ID (e.g. res-onc-001)")
    name: str = Field(..., description="Full display name")
    email: str = Field(..., description="Researcher corporate/academic email")
    institute_id: str = Field(..., description="Affiliated Institute ID")
    telemetry_usage: ResearcherTelemetryUsage = Field(default_factory=ResearcherTelemetryUsage)
    sku_attributions: List[ResearcherSKUAttribution] = Field(default_factory=list)
    total_allocated_cost: float = Field(0.0, description="Sum of all allocated SKU costs")


class SharedOverheadDetail(BaseModel):
    """Shared and administrative room overhead attribution."""
    admin_usage: ResearcherTelemetryUsage = Field(default_factory=ResearcherTelemetryUsage)
    sku_attributions: List[ResearcherSKUAttribution] = Field(default_factory=list)
    total_shared_overhead_cost: float = Field(0.0, description="Total shared overhead cost")


class CostDriversBreakdown(BaseModel):
    """Breakdown by architectural cost driver."""
    storage_cost: float = Field(0.0, description="Cloud Storage cost in USD")
    compute_notebooks_cost: float = Field(0.0, description="Compute Engine / Colab Enterprise VM/GPU cost")
    bigquery_cost: float = Field(0.0, description="BigQuery query analysis cost")
    network_egress_cost: float = Field(0.0, description="Data transfer / egress bandwidth cost")
    vertex_ai_cost: float = Field(0.0, description="Vertex AI & Gemini token cost")
    other_cost: float = Field(0.0, description="Other auxiliary GCP services cost")


class CapacityTrackingMetrics(BaseModel):
    """Physical capacity consumed across research rooms."""
    storage_volume_bytes: int = Field(0, description="Total storage bytes across buckets")
    compute_core_hours: float = Field(0.0, description="Notebook VM/GPU runtime hours")
    bigquery_bytes_scanned: int = Field(0, description="Total BigQuery bytes scanned/billed")
    bigquery_slot_hours: float = Field(0.0, description="BigQuery slots consumed")
    ai_token_count: int = Field(0, description="Total Vertex AI / Gemini tokens")
    ai_calls_count: int = Field(0, description="Total AI API inferences")


class RoomBudgetRunway(BaseModel):
    """Actual spend vs grant ceiling and burn-rate runway."""
    room_id: str = Field(..., description="Research Room identifier")
    room_name: str = Field(..., description="Research Room display name")
    budget_limit_usd: float = Field(5000.0, description="Allocated grant ceiling")
    cumulative_spend_usd: float = Field(0.0, description="Inception to date cumulative spend")
    budget_utilization_pct: float = Field(0.0, description="Percentage of grant ceiling used")
    daily_burn_rate_usd: float = Field(0.0, description="Average daily spend rate")
    projected_runway_days: Optional[float] = Field(None, description="Days remaining until budget exhaustion")
    status: str = Field("HEALTHY", description="'HEALTHY', 'WARNING', or 'OVERRUN'")


class FinOpsAnomalyAlert(BaseModel):
    """Automated alert for cost overruns, idle resources, or usage surges."""
    alert_id: str = Field(..., description="Unique alert UUID")
    room_id: Optional[str] = Field(None, description="Associated Research Room ID")
    severity: str = Field("WARNING", description="'INFO', 'WARNING', or 'CRITICAL'")
    title: str = Field(..., description="Alert headline")
    description: str = Field(..., description="Root cause explanation")
    metric_name: str = Field(..., description="Metric triggering the alert")
    detected_value: float = Field(0.0, description="Detected telemetry value")
    threshold_value: float = Field(0.0, description="Policy threshold value")
    created_at: str = Field(..., description="Detection timestamp")


class RoomFinOpsDetailResponse(BaseModel):
    """Hierarchical FinOps breakdown for a single Research Room."""
    room_id: str = Field(..., description="Research Room identifier")
    room_name: str = Field(..., description="Research Room display name")
    spoke_project_id: str = Field(..., description="GCP Spoke Project ID")
    institute_id: str = Field(..., description="Primary tenant Institute ID")
    budget_limit_usd: float = Field(5000.0, description="Allocated room grant budget")
    total_invoiced_cost: float = Field(0.0, description="100% Invoiced project cost")
    currency: str = Field("USD", description="Currency code")
    created_at: Optional[str] = Field(None, description="Room provisioning timestamp")
    spend_since_creation: float = Field(0.0, description="Cumulative spend since room creation date")
    cost_drivers: CostDriversBreakdown = Field(default_factory=CostDriversBreakdown)
    capacity: CapacityTrackingMetrics = Field(default_factory=CapacityTrackingMetrics)
    skus: List[SKUBillingItem] = Field(default_factory=list)
    researchers: List[ResearcherCostDetail] = Field(default_factory=list)
    shared_overhead: SharedOverheadDetail = Field(default_factory=SharedOverheadDetail)
    reconciliation_variance: float = Field(0.0)
    reconciliation_status: str = Field("BALANCED")


class ProjectCostItem(BaseModel):
    """Project-level billing export invoice summary."""
    project_id: str = Field(..., description="GCP Project ID")
    room_id: Optional[str] = Field(None, description="Linked Research Room ID")
    total_cost: float = Field(0.0, description="Total invoiced cost")
    currency: str = Field("USD", description="Currency code")


class InstituteCostBreakdown(BaseModel):
    """Cross-room aggregate cost attribution for a tenant Institute."""
    institute_id: str = Field(..., description="Tenant Institute ID")
    institute_name: str = Field(..., description="Institute display name")
    total_allocated_cost: float = Field(0.0, description="Total allocated cost")
    currency: str = Field("USD", description="Currency code")
    invoice_month: str = Field(..., description="Invoice period")
    researcher_count: int = Field(0, description="Affiliated researchers count")
    rooms_involved: List[str] = Field(default_factory=list)
    researchers: List[ResearcherCostDetail] = Field(default_factory=list)
    sku_breakdown: List[SKUBillingItem] = Field(default_factory=list)


class FinOpsForecastResponse(BaseModel):
    """Run-rate based cost forecast for the current billing cycle."""
    invoice_month: str = Field(..., description="Billing invoice month")
    days_elapsed: int = Field(..., description="Days elapsed in cycle")
    days_in_month: int = Field(..., description="Total days in month")
    current_mtd_cost: float = Field(..., description="Actual MTD spend")
    daily_run_rate: float = Field(..., description="Average daily spend rate")
    forecasted_monthly_cost: float = Field(..., description="Projected spend")
    currency: str = Field("USD", description="Currency code")
    forecast_confidence: float = Field(0.95)


class FinOpsSummaryResponse(BaseModel):
    """Fleet-wide FinOps executive overview and project cost breakdown."""
    invoice_month: str = Field(..., description="Invoice month")
    start_date: Optional[str] = Field(None)
    end_date: Optional[str] = Field(None)
    min_creation_date: Optional[str] = Field("2026-09-24T08:00:00Z", description="Earliest project creation timestamp across fleet")
    total_grant_budget: float = Field(28500.0, description="Sum of all allocated research room grant ceilings")
    total_fleet_cost: float = Field(0.0, description="Total period cost across all projects")
    cumulative_inception_cost: float = Field(0.0, description="Cumulative spend from inception to date")
    spend_since_inception: float = Field(0.0, description="Cumulative spend from earliest project creation to present")
    total_researcher_cost: float = Field(0.0, description="Total cost allocated to researchers")
    total_shared_overhead_cost: float = Field(0.0, description="Total room shared/admin overhead")
    hub_infrastructure_cost: float = Field(0.0, description="Central hub portal cost")
    forecasted_monthly_cost: float = Field(0.0, description="Projected full-month fleet spend")
    currency: str = Field("USD", description="Currency code")
    cost_drivers: CostDriversBreakdown = Field(default_factory=CostDriversBreakdown)
    capacity: CapacityTrackingMetrics = Field(default_factory=CapacityTrackingMetrics)
    runway_metrics: List[RoomBudgetRunway] = Field(default_factory=list)
    anomaly_alerts: List[FinOpsAnomalyAlert] = Field(default_factory=list)
    projects: List[ProjectCostItem] = Field(default_factory=list)
    institutes: List[InstituteCostBreakdown] = Field(default_factory=list)
    rooms: List[RoomFinOpsDetailResponse] = Field(default_factory=list)
    sku_summary: List[SKUBillingItem] = Field(default_factory=list)


class FinOpsAllocationMatrixResponse(BaseModel):
    """Multi-dimensional allocation matrix (Institute -> Room -> Researcher)."""
    invoice_month: str = Field(..., description="Invoice month")
    total_allocated_cost: float = Field(0.0)
    currency: str = Field("USD", description="Currency code")
    reconciliation_status: str = Field("BALANCED")
    total_invoice_cost: float = Field(0.0)
    total_researcher_allocated_cost: float = Field(0.0)
    total_shared_overhead_cost: float = Field(0.0)
    total_hub_infrastructure_cost: float = Field(0.0)
    variance: float = Field(0.0)
    matrix: Dict[str, Dict[str, List[ResearcherCostDetail]]] = Field(default_factory=dict)


# Backward-compatible aliases
SKUCostBreakdown = SKUBillingItem
ResearcherCostAttribution = ResearcherCostDetail
RoomCostBreakdown = RoomFinOpsDetailResponse
