"""
Resources & Infrastructure API Endpoints
Provides cloud asset mapping, storage bucket management, shared datasets, and runtime templates.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
try:
    from backend.app.models.infrastructure import (
        InfrastructureOverviewResponse,
        StorageBucketItem,
        SharedDatasetItem,
        NotebookRuntimeTemplate,
        BucketLinkRequest,
        BucketDetachRequest
    )
    from backend.app.services.infrastructure import InfrastructureService
except ImportError:
    from app.models.infrastructure import (
        InfrastructureOverviewResponse,
        StorageBucketItem,
        SharedDatasetItem,
        NotebookRuntimeTemplate,
        BucketLinkRequest,
        BucketDetachRequest
    )
    from app.services.infrastructure import InfrastructureService

router = APIRouter(prefix="/resources", tags=["resources"])


def get_infra_service() -> InfrastructureService:
    return InfrastructureService()


@router.get("/overview", response_model=InfrastructureOverviewResponse)
def get_infrastructure_overview(
    service: InfrastructureService = Depends(get_infra_service)
):
    """Returns aggregated physical cloud infrastructure, VPCs, buckets, shared datasets, and runtime templates."""
    try:
        return service.get_infrastructure_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve infrastructure topology: {str(e)}")


@router.get("/buckets", response_model=List[StorageBucketItem])
def list_storage_buckets(
    service: InfrastructureService = Depends(get_infra_service)
):
    """Returns list of storage buckets in hub and spoke projects."""
    try:
        overview = service.get_infrastructure_overview()
        return overview.storage_buckets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list storage buckets: {str(e)}")


@router.get("/datasets", response_model=List[SharedDatasetItem])
def list_shared_datasets(
    service: InfrastructureService = Depends(get_infra_service)
):
    """Returns list of central shared clinical and reference datasets with their schemas."""
    try:
        overview = service.get_infrastructure_overview()
        return overview.shared_datasets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list shared datasets: {str(e)}")


@router.get("/templates", response_model=List[NotebookRuntimeTemplate])
def list_notebook_templates(
    service: InfrastructureService = Depends(get_infra_service)
):
    """Returns configured Colab Enterprise and Vertex AI compute runtime templates."""
    try:
        overview = service.get_infrastructure_overview()
        return overview.notebook_templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list notebook templates: {str(e)}")


@router.post("/buckets/link")
def link_storage_bucket(
    request: BucketLinkRequest,
    service: InfrastructureService = Depends(get_infra_service)
):
    """Links a storage bucket to a research room."""
    try:
        return service.link_storage_bucket(
            room_id=request.room_id,
            bucket_name=request.bucket_name,
            role_type=request.role_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link storage bucket: {str(e)}")


@router.post("/buckets/detach")
def detach_storage_bucket(
    request: BucketDetachRequest,
    service: InfrastructureService = Depends(get_infra_service)
):
    """Detaches a storage bucket from a research room."""
    try:
        return service.detach_storage_bucket(
            room_id=request.room_id,
            bucket_name=request.bucket_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detach storage bucket: {str(e)}")
