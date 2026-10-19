"""FinOps REST API Endpoints for cost summary, researcher attribution, and allocation matrix."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.models.finops import (
    FinOpsAllocationMatrixResponse,
    FinOpsForecastResponse,
    FinOpsSummaryResponse,
    InstituteCostBreakdown,
    ResearcherCostDetail,
    RoomFinOpsDetailResponse,
)
from backend.app.services.finops import FinOpsService, get_finops_service

logger = logging.getLogger("finops_api")

router = APIRouter(prefix="/finops", tags=["FinOps Cost Attribution"])


@router.get(
    "/summary",
    response_model=FinOpsSummaryResponse,
    summary="Get fleet-wide FinOps summary, project breakdown, and overhead reconciliation",
)
def get_finops_summary(
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM), e.g. '202609'"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> FinOpsSummaryResponse:
    """Retrieve overall fleet spend, project-level, institute-level aggregations, overhead, and run-rate forecast."""
    try:
        return service.get_summary(
            invoice_month=invoice_month,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Error generating FinOps summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate FinOps summary: {str(e)}",
        )


@router.get(
    "/researchers",
    response_model=List[ResearcherCostDetail],
    summary="List researcher-level cost attributions",
)
def get_researcher_attributions(
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM)"),
    room_id: Optional[str] = Query(None, description="Filter by Research Room ID"),
    institute_id: Optional[str] = Query(None, description="Filter by Institute ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> List[ResearcherCostDetail]:
    """Retrieve fine-grained cost allocations apportioned to each individual researcher."""
    try:
        return service.get_researcher_attributions(
            invoice_month=invoice_month,
            room_id=room_id,
            institute_id=institute_id,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching researcher attributions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch researcher cost attributions: {str(e)}",
        )


@router.get(
    "/researchers/{user_email:path}/spend",
    summary="Get aggregated spend of a researcher across all research rooms",
)
def get_researcher_spend(
    user_email: str,
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> dict:
    """Retrieve multi-room aggregated spend, room-by-room breakdown, and SKU attributions for a researcher."""
    try:
        return service.get_researcher_spend(
            email=user_email,
            invoice_month=invoice_month,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Error fetching spend for researcher {user_email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate researcher spend: {str(e)}",
        )


@router.get(
    "/rooms/{room_id}",
    response_model=RoomFinOpsDetailResponse,
    summary="Get cost breakdown, researcher allocations, and shared overhead for a Research Room",
)
def get_room_cost(
    room_id: str,
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> RoomFinOpsDetailResponse:
    """Retrieve complete invoiced cost, researcher weight allocations, and shared overhead for a single Research Room."""
    try:
        return service.get_room_cost(
            room_id=room_id,
            invoice_month=invoice_month,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error retrieving cost for room {room_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve room cost breakdown: {str(e)}",
        )


@router.get(
    "/institutes/{institute_id}",
    response_model=InstituteCostBreakdown,
    summary="Get cross-room aggregated cost for an Institute",
)
def get_institute_cost(
    institute_id: str,
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> InstituteCostBreakdown:
    """Retrieve aggregate cost allocated to all researchers affiliated with the specified institute."""
    try:
        return service.get_institute_cost(
            institute_id=institute_id,
            invoice_month=invoice_month,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error retrieving cost for institute {institute_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve institute cost breakdown: {str(e)}",
        )


@router.get(
    "/matrix",
    response_model=FinOpsAllocationMatrixResponse,
    summary="Get full multi-dimensional cost allocation matrix and invoice reconciliation",
)
def get_allocation_matrix(
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> FinOpsAllocationMatrixResponse:
    """Retrieve the full hierarchical matrix (Institute -> Room -> Researcher -> SKU) and invoice reconciliation status."""
    try:
        return service.get_allocation_matrix(
            invoice_month=invoice_month,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Error generating allocation matrix: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate allocation matrix: {str(e)}",
        )


@router.get(
    "/forecast",
    response_model=FinOpsForecastResponse,
    summary="Get run-rate cost projection for current billing cycle",
)
def get_forecast(
    invoice_month: Optional[str] = Query(None, description="Billing month (YYYYMM)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    service: FinOpsService = Depends(get_finops_service),
) -> FinOpsForecastResponse:
    """Retrieve Month-To-Date run-rate and full month projected spend."""
    try:
        return service.get_forecast(
            invoice_month=invoice_month,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Error generating cost forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate cost forecast: {str(e)}",
        )
