"""API router for 5-Item Regulatory Checklist, Onboarding Gate, and IAM Enforcement."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.compliance import (
    ComplianceHorizonReport,
    ComplianceScanResult,
    CreateRoomRequest,
    OnboardingGateRequest,
    OnboardingGateResponse,
    RoomComplianceSummary,
    RoomRequestResponse,
)
from backend.app.services.compliance import ComplianceService, get_compliance_service

router = APIRouter(tags=["compliance"])


@router.post(
    "/enforce",
    response_model=List[ComplianceScanResult],
    summary="Enforce fleet-wide IAM compliance policies",
    description="Syncs active research room IAM policies based on the latest BigQuery regulatory scan.",
)
def enforce_fleet_compliance(
    service: ComplianceService = Depends(get_compliance_service),
) -> List[ComplianceScanResult]:
    """Execute fleet-wide IAM synchronization for all active provisioned rooms."""
    return service.enforce_fleet_compliance()


@router.get(
    "/summary",
    response_model=List[RoomComplianceSummary],
    summary="Get fleet-wide compliance summaries for all active rooms",
)
def get_compliance_summary(
    service: ComplianceService = Depends(get_compliance_service),
) -> List[RoomComplianceSummary]:
    """Retrieve compliance status summaries across all active research rooms."""
    return service.list_all_summaries()


@router.get(
    "/rooms/{room_id}",
    response_model=RoomComplianceSummary,
    summary="Get research room regulatory compliance status",
)
def get_room_compliance(
    room_id: str,
    service: ComplianceService = Depends(get_compliance_service),
) -> RoomComplianceSummary:
    """Retrieve current regulatory compliance status for a research room."""
    return service.get_room_compliance(room_id)


@router.post(
    "/rooms/{room_id}/scan",
    response_model=ComplianceScanResult,
    summary="Trigger on-demand compliance scan and IAM sync on active room",
)
def scan_room_compliance(
    room_id: str,
    service: ComplianceService = Depends(get_compliance_service),
) -> ComplianceScanResult:
    """Execute ongoing compliance scan and IAM sync on an active research room."""
    return service.scan_room_compliance(room_id)


@router.get(
    "/requests/{request_id}/gate",
    response_model=OnboardingGateResponse,
    summary="Get pre-flight onboarding compliance gate decision for a request",
)
def get_onboarding_gate(
    request_id: str,
    service: ComplianceService = Depends(get_compliance_service),
) -> OnboardingGateResponse:
    """Retrieve pre-flight onboarding gate decision for a prospective room request without payload mutations."""
    req = OnboardingGateRequest(request_id=request_id)
    return service.evaluate_onboarding_gate(req)


@router.post(
    "/requests/{request_id}/evaluate-gate",
    response_model=OnboardingGateResponse,
    summary="Evaluate pre-flight onboarding compliance gate",
)
def evaluate_onboarding_gate(
    request_id: str,
    request: Optional[OnboardingGateRequest] = None,
    service: ComplianceService = Depends(get_compliance_service),
) -> OnboardingGateResponse:
    """Execute pre-flight onboarding gate scan on a prospective room request."""
    req = request or OnboardingGateRequest(request_id=request_id)
    if req.request_id != request_id:
        req.request_id = request_id
    return service.evaluate_onboarding_gate(req)


@router.get(
    "/horizons",
    response_model=ComplianceHorizonReport,
    summary="Get fleet-wide compliance horizon expiration forecast",
)
def get_compliance_horizons(
    service: ComplianceService = Depends(get_compliance_service),
) -> ComplianceHorizonReport:
    """Retrieve fleet-wide compliance expiration horizon forecast."""
    return service.get_horizon_report()


@router.get(
    "/requests",
    response_model=List[RoomRequestResponse],
    summary="Get all prospective Research Room onboarding requests",
)
def get_room_requests(
    service: ComplianceService = Depends(get_compliance_service),
) -> List[RoomRequestResponse]:
    """Retrieve all prospective Research Room requests from BigQuery."""
    return service.get_room_requests()


@router.post(
    "/requests",
    response_model=RoomRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit and ingest a new Research Room request",
)
def create_room_request(
    request: CreateRoomRequest,
    service: ComplianceService = Depends(get_compliance_service),
) -> RoomRequestResponse:
    """Submit a new Research Room request, evaluate pre-flight gate, and ingest to BigQuery ops_room_requests."""
    try:
        return service.create_room_request(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create room request: {str(e)}",
        )

