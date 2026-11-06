"""API router for Research Rooms lifecycle, DUA compliance, and IAM governance."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.models.rooms import (
    AddResearcherRequest,
    AddResearcherResponse,
    DowngradeRequest,
    ResearchRoomDetail,
    ResearchRoomSummary,
    RoomActionResponse,
    StatusUpdateRequest,
    SuspendRequest,
)
from backend.app.services.fleet import FleetGovernanceService, get_fleet_service

router = APIRouter(tags=["rooms"])


@router.get(
    "",
    response_model=List[ResearchRoomSummary],
    summary="List all research rooms",
    description="Lists all research rooms with health status, DUA countdowns, researcher counts, and package summaries.",
)
@router.get(
    "/",
    response_model=List[ResearchRoomSummary],
    include_in_schema=False,
)
def list_rooms(
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> List[ResearchRoomSummary]:
    """Retrieve summary of all research rooms across the spoke fleet from BigQuery."""
    return service.get_rooms()


@router.get(
    "/{room_id}",
    response_model=ResearchRoomDetail,
    summary="Get research room details",
    description="Detailed room view including researcher roster, datasets, storage bucket URIs, and VPC/runtime info.",
)
def get_room(
    room_id: str,
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> ResearchRoomDetail:
    """Retrieve detailed specification and runtime state for a single room from BigQuery."""
    room = service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research room '{room_id}' not found in registry",
        )
    return room


@router.get(
    "/{room_id}/packages",
    response_model=Dict[str, Any],
    summary="Get room software packages & datasets",
    description="Returns all subscribed hub datasets, local tables, analytical notebooks, and installed packages.",
)
def get_room_packages(
    room_id: str,
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> Dict[str, Any]:
    """Retrieve software packages and dataset subscriptions for a room."""
    packages = service.get_room_packages(room_id)
    if not packages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research room '{room_id}' not found in registry",
        )
    return packages


@router.post(
    "/{room_id}/status",
    response_model=RoomActionResponse,
    summary="Update research room status & IAM policy",
    description="Updates operational status (ACTIVE, SOFT_DOWNGRADED, SUSPENDED) and mutates spoke IAM bindings.",
)
def update_room_status(
    room_id: str,
    request: StatusUpdateRequest,
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> RoomActionResponse:
    """Update research room status in BigQuery and enforce live IAM policy on spoke project."""
    try:
        result = service.update_room_status(room_id, request.new_status, reason=request.reason)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research room '{room_id}' not found in registry",
            )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{room_id}/downgrade",
    response_model=RoomActionResponse,
    summary="Downgrade research room IAM permissions",
    description="Toggles researcher IAM role to read-only/downgraded state for compliance enforcement.",
)
def downgrade_room(
    room_id: str,
    request: DowngradeRequest = DowngradeRequest(),
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> RoomActionResponse:
    """Enforce soft-downgrade on research room when IRB or DUA is expired."""
    result = service.downgrade_room(room_id, request)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research room '{room_id}' not found in registry",
        )
    return result


@router.post(
    "/{room_id}/reactivate",
    response_model=RoomActionResponse,
    summary="Reactivate research room IAM permissions",
    description="Restores full researcher active access following compliance renewal.",
)
def reactivate_room(
    room_id: str,
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> RoomActionResponse:
    """Reactivate research room and restore full researcher permissions."""
    result = service.reactivate_room(room_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research room '{room_id}' not found in registry",
        )
    return result


@router.post(
    "/{room_id}/suspend",
    response_model=RoomActionResponse,
    summary="Suspend research room IAM permissions",
    description="Suspends research room and completely revokes researcher IAM permissions.",
)
def suspend_room(
    room_id: str,
    request: SuspendRequest = SuspendRequest(),
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> RoomActionResponse:
    """Suspend research room and revoke all researcher access from spoke project."""
    result = service.suspend_room(room_id, request)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research room '{room_id}' not found in registry",
        )
    return result


@router.post(
    "/{room_id}/researchers",
    response_model=AddResearcherResponse,
    summary="Add researcher stub to room",
    description="Safe pass-through stub for provisioning a researcher account in a research room.",
)
def add_researcher(
    room_id: str,
    request: AddResearcherRequest,
    service: FleetGovernanceService = Depends(get_fleet_service),
) -> AddResearcherResponse:
    """Add a researcher stub to the specified research room."""
    # Verify room exists first
    room = service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research room '{room_id}' not found in registry",
        )
    return service.add_researcher_stub(room_id, request.researcher_email, request.role or "Researcher")
