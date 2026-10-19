"""
Pydantic Models for Cloud Infrastructure, Buckets & Environment Management
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StorageBucketItem(BaseModel):
    bucket_name: str
    project_id: str
    room_id: Optional[str] = None
    role_type: str = Field(..., description="INBOUND, EXPORT, HUB_APPROVALS, HUB_STAGING, SYSTEM, CUSTOM")
    location: str = "me-west1"
    storage_class: str = "STANDARD"
    is_linked: bool = True
    object_count: int = 0
    total_bytes: int = 0
    uniform_bucket_level_access: bool = True
    retention_days: int = 7


class BucketLinkRequest(BaseModel):
    room_id: str
    bucket_name: str
    role_type: str = "INBOUND"


class BucketDetachRequest(BaseModel):
    room_id: str
    bucket_name: str


class VpcNetworkItem(BaseModel):
    network_name: str
    project_id: str
    room_id: Optional[str] = None
    subnet_name: str
    ip_cidr_range: str
    region: str = "me-west1"
    private_google_access: bool = True
    vpc_sc_perimeter: str = "health-data-enclave-perimeter"


class SharedDatasetTable(BaseModel):
    table_id: str
    row_count: int
    bytes_billed: int = 0
    description: str
    schema_fields: List[str] = []


class SharedDatasetItem(BaseModel):
    dataset_id: str
    project_id: str = "gcp-rr-hub-core"
    description: str
    tables: List[SharedDatasetTable]
    subscribed_rooms: List[str] = []
    authorization_type: str = "AUTHORIZED_DATASET"


class NotebookRuntimeTemplate(BaseModel):
    template_id: str
    title: str
    machine_type: str
    vcpus: int
    ram_gb: int
    gpu_type: Optional[str] = None
    boot_disk_gb: int
    disk_type: str = "pd-balanced"
    container_image: str
    idle_shutdown_minutes: int
    preinstalled_libraries: List[str]
    target_workloads: str


class InfrastructureOverviewResponse(BaseModel):
    hub_project_id: str
    region: str
    vpcs: List[VpcNetworkItem]
    storage_buckets: List[StorageBucketItem]
    shared_datasets: List[SharedDatasetItem]
    notebook_templates: List[NotebookRuntimeTemplate]
    summary_counts: Dict[str, int]
