"""API router for Airlock Data Egress Governance and Gemini Risk Scanner."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.models.airlock import (
    AirlockActionRequest,
    AirlockActionResponse,
    AirlockExportCandidate,
    AirlockScanRequest,
)
from backend.app.services.gemini_risk_service import (
    GeminiRiskService,
    get_gemini_risk_service,
)

router = APIRouter(tags=["airlock"])


@router.get(
    "/candidates",
    response_model=List[AirlockExportCandidate],
    summary="List candidate egress files across spoke research rooms",
)
@router.get(
    "/airlock/candidates",
    response_model=List[AirlockExportCandidate],
    include_in_schema=False,
)
async def list_airlock_candidates(
    room_id: Optional[str] = Query(None, description="Optional room ID filter"),
    service: GeminiRiskService = Depends(get_gemini_risk_service),
) -> List[AirlockExportCandidate]:
    """List all candidate export CSV files staged in spoke export buckets with their Gemini scan ratings."""
    return service.list_candidates(room_id=room_id)


@router.post(
    "/scan",
    response_model=AirlockExportCandidate,
    summary="Trigger on-demand Gemini AI privacy scan on an export file",
)
@router.post(
    "/airlock/scan",
    response_model=AirlockExportCandidate,
    include_in_schema=False,
)
async def scan_airlock_file(
    request: AirlockScanRequest,
    service: GeminiRiskService = Depends(get_gemini_risk_service),
) -> AirlockExportCandidate:
    """Analyze a staged candidate export file with Gemini Flash for PII, HIPAA Safe Harbor, and cell count violations."""
    if not request.file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_name is required for targeted Gemini AI scanning.",
        )
    try:
        return service.scan_export_file(room_id=request.room_id, file_name=request.file_name)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini AI Privacy Scan failed: {str(e)}",
        )


@router.post(
    "/action",
    response_model=AirlockActionResponse,
    summary="Record administrative approval or quarantine decision",
)
@router.post(
    "/airlock/action",
    response_model=AirlockActionResponse,
    include_in_schema=False,
)
async def take_airlock_action(
    request: AirlockActionRequest,
    service: GeminiRiskService = Depends(get_gemini_risk_service),
) -> AirlockActionResponse:
    """Approve or reject a candidate data egress export."""
    try:
        return service.take_decision(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record airlock decision: {str(e)}",
        )
