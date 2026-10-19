"""Telemetry, BigQuery execution metrics, and room asset inventory API endpoints."""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.models.telemetry import (
    AuditLogEvent,
    DailyComputeMetricItem,
    FleetTelemetryOverview,
    MonthlyUsageRollupItem,
    NotebookSessionItem,
    QueryJobItem,
    RoomActivitySummary,
    RoomAssetInventory,
    TelemetrySyncResponse,
)
from backend.app.services.telemetry import TelemetryService, get_telemetry_service

logger = logging.getLogger("telemetry_api")

router = APIRouter()


def _clean_str(val: Any) -> Optional[str]:
    """Extract clean string value ignoring FastAPI Query objects."""
    return str(val).strip() if isinstance(val, str) and val.strip() else None


def _clean_int(val: Any, default: int = 50) -> int:
    """Extract clean integer value ignoring FastAPI Query objects."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


@router.get(
    "/overview",
    response_model=FleetTelemetryOverview,
    summary="Get fleet-wide operational telemetry overview",
)
def get_fleet_overview(
    service: TelemetryService = Depends(get_telemetry_service),
) -> FleetTelemetryOverview:
    """Return aggregated active researchers, 24h queries, 30d bytes scanned, and total fleet storage."""
    try:
        return service.get_fleet_overview()
    except Exception as e:
        logger.error("Failed fetching fleet overview: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed fetching fleet overview: {str(e)}",
        )


@router.get(
    "/queries",
    response_model=List[QueryJobItem],
    summary="List BigQuery execution jobs across rooms and researchers",
)
def get_queries(
    room_id: Optional[str] = Query(None, description="Optional filter by research room ID"),
    user_email: Optional[str] = Query(None, description="Optional filter by researcher email"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of query jobs to retrieve"),
    service: TelemetryService = Depends(get_telemetry_service),
) -> List[QueryJobItem]:
    """Retrieve sanitized BigQuery execution history with duration, bytes billed, and slot milliseconds."""
    try:
        return service.get_queries(
            room_id=_clean_str(room_id),
            user_email=_clean_str(user_email),
            limit=_clean_int(limit, default=50),
        )
    except Exception as e:
        logger.error("Failed fetching query history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed fetching query history: {str(e)}",
        )


@router.get(
    "/audit-feed",
    response_model=List[AuditLogEvent],
    summary="Get audit log feed from hub telemetry",
)
@router.get(
    "/audit",
    response_model=List[AuditLogEvent],
    summary="Get audit log feed from hub telemetry (alias)",
    include_in_schema=False,
)
def get_audit_feed(
    room_id: Optional[str] = Query(None, description="Optional filter by research room ID"),
    principal_email: Optional[str] = Query(None, description="Optional filter by user principal email"),
    category: Optional[str] = Query(None, description="Optional filter by telemetry category"),
    researchers_only: bool = Query(False, description="Filter strictly for enrolled researcher events"),
    limit: Optional[int] = Query(None, ge=1, le=5000, description="Maximum number of audit events to retrieve"),
    service: TelemetryService = Depends(get_telemetry_service),
) -> List[AuditLogEvent]:
    """Retrieve security and governance audit log feed from ops_audit_events_curated."""
    try:
        clean_limit = int(limit) if limit is not None else None
        return service.get_audit_feed(
            room_id=_clean_str(room_id),
            category=_clean_str(category),
            principal_email=_clean_str(principal_email),
            researchers_only=bool(researchers_only),
            limit=clean_limit,
        )
    except Exception as e:
        logger.error("Failed fetching audit feed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed fetching audit feed: {str(e)}",
        )


@router.get(
    "/metrics/daily",
    response_model=List[DailyComputeMetricItem],
    summary="Get persisted daily compute usage metrics",
)
def get_daily_compute_metrics(
    room_id: Optional[str] = Query(None, description="Optional filter by room ID"),
    user_email: Optional[str] = Query(None, description="Optional filter by researcher email"),
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return"),
    service: TelemetryService = Depends(get_telemetry_service),
) -> List[DailyComputeMetricItem]:
    """Retrieve daily aggregated compute and slot metrics from ops_daily_compute_metrics."""
    try:
        return service.get_daily_compute_metrics(
            room_id=_clean_str(room_id),
            user_email=_clean_str(user_email),
            limit=_clean_int(limit, default=50),
        )
    except Exception as e:
        logger.error("Failed fetching daily compute metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed fetching daily compute metrics: {str(e)}",
        )


@router.get(
    "/metrics/monthly",
    response_model=List[MonthlyUsageRollupItem],
    summary="Get monthly usage rollup metrics per room",
)
def get_monthly_usage_rollup(
    room_id: Optional[str] = Query(None, description="Optional filter by room ID"),
    institute_id: Optional[str] = Query(None, description="Optional filter by institute ID"),
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return"),
    service: TelemetryService = Depends(get_telemetry_service),
) -> List[MonthlyUsageRollupItem]:
    """Retrieve monthly rollup metrics from ops_monthly_usage_rollup."""
    try:
        return service.get_monthly_usage_rollup(
            room_id=_clean_str(room_id),
            institute_id=_clean_str(institute_id),
            limit=_clean_int(limit, default=50),
        )
    except Exception as e:
        logger.error("Failed fetching monthly usage rollup: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed fetching monthly usage rollup: {str(e)}",
        )


@router.get(
    "/notebooks/sessions",
    response_model=List[NotebookSessionItem],
    summary="Get persisted Colab Enterprise and BigQuery Studio notebook sessions",
)
def get_notebook_sessions(
    room_id: Optional[str] = Query(None, description="Optional filter by room ID"),
    user_email: Optional[str] = Query(None, description="Optional filter by researcher email"),
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return"),
    service: TelemetryService = Depends(get_telemetry_service),
) -> List[NotebookSessionItem]:
    """Retrieve Colab Enterprise notebook sessions with machine type and runtime templates."""
    try:
        return service.get_notebook_sessions(
            room_id=_clean_str(room_id),
            user_email=_clean_str(user_email),
            limit=_clean_int(limit, default=50),
        )
    except Exception as e:
        logger.error("Failed fetching notebook sessions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed fetching notebook sessions: {str(e)}",
        )


@router.post(
    "/sync",
    response_model=TelemetrySyncResponse,
    summary="Trigger BigQuery curation and aggregation stored procedures",
)
def trigger_telemetry_sync(
    service: TelemetryService = Depends(get_telemetry_service),
) -> TelemetrySyncResponse:
    """Execute BigQuery stored procedures to synchronize curated audit events and rollups."""
    try:
        return service.sync_telemetry_pipelines()
    except Exception as e:
        logger.error("Failed triggering telemetry sync: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed triggering telemetry sync: {str(e)}",
        )


@router.get(
    "/rooms/{room_id}/inventory",
    response_model=RoomAssetInventory,
    summary="Get BigQuery tables, Cloud Storage sizes, and notebook counts for a room",
)
def get_room_inventory(
    room_id: str,
    service: TelemetryService = Depends(get_telemetry_service),
) -> RoomAssetInventory:
    """Retrieve asset inventory for a specific research room."""
    try:
        return service.get_room_inventory(room_id=room_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error("Failed retrieving inventory for room %s: %s", room_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed retrieving room inventory: {str(e)}",
        )


@router.get(
    "/rooms/{room_id}/activity",
    response_model=RoomActivitySummary,
    summary="Get recent queries, audit events, and last active session for a room",
)
def get_room_activity(
    room_id: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of items to retrieve"),
    researchers_only: bool = Query(True, description="Filter for enrolled researcher activity"),
    service: TelemetryService = Depends(get_telemetry_service),
) -> RoomActivitySummary:
    """Retrieve recent queries, audit events, and last active session for a research room."""
    try:
        return service.get_room_activity(
            room_id=room_id,
            limit=_clean_int(limit, default=50),
            researchers_only=bool(researchers_only),
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error("Failed retrieving activity for room %s: %s", room_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed retrieving room activity: {str(e)}",
        )
