"""API router for Partner Research Institutes registry using live BigQuery."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.rooms import InstituteSummary
from backend.app.services.fleet import FleetGovernanceService, get_fleet_service

router = APIRouter(tags=["institutes"])


@router.get(
    "",
    response_model=List[InstituteSummary],
    summary="List all partner institutes",
    description="Lists registered partner institutes and their affiliated research rooms from BigQuery.",
)
@router.get(
    "/",
    response_model=List[InstituteSummary],
    include_in_schema=False,
)
async def list_institutes(
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> List[InstituteSummary]:
    """Retrieve all registered academic and medical research institutes from BigQuery."""
    return service.get_institutes()


@router.get(
    "/{institute_id}",
    response_model=InstituteSummary,
    summary="Get institute details",
    description="Retrieves a specific partner institute and affiliated rooms by its identifier.",
)
async def get_institute(
    institute_id: str,
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> InstituteSummary:
    """Retrieve details and affiliated rooms for a single institute from BigQuery."""
    inst = service.get_institute(institute_id)
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partner institute '{institute_id}' not found in registry",
        )
    return inst
