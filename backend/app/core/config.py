"""Application configuration module using Pydantic Settings with defensive fallback."""

import os
from functools import lru_cache
from typing import List

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    
    class Settings(BaseSettings):
        """Configuration settings for GCP Health Data Platform Central Administrator Portal."""

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            case_sensitive=True,
        )

        # Core GCP Configuration
        GCP_PROJECT_ID: str = "gcp-rr-hub-core"
        GCP_REGION: str = "me-west1"
        ADMIN_DOMAIN: str = "liatsabag.altostrat.com"

        # BigQuery Billing Configuration
        BILLING_PROJECT_ID: str = "gcp-rr-hub-core"
        BILLING_DATASET_ID: str = "billing"
        BILLING_EXPORT_TABLE: str = "gcp_billing_export_v1"

        # BigQuery Hub Datasets
        HUB_REGISTRY_DATASET: str = "hub_registry"
        HUB_TELEMETRY_DATASET: str = "hub_telemetry"

        # Vertex AI GenAI Configuration
        VERTEX_AI_MODEL: str = "gemini-3.7-flash"
        VERTEX_AI_LOCATION: str = "me-west1"

        # API & Networking Configuration
        CORS_ORIGINS: List[str] = ["*"]
        API_V1_PREFIX: str = "/api/v1"
        ENVIRONMENT: str = "development"

except ImportError:
    from pydantic import BaseModel

    class Settings(BaseModel):  # type: ignore[no-redef]
        """Fallback configuration settings using pure Pydantic BaseModel and env vars."""

        GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "gcp-rr-hub-core")
        GCP_REGION: str = os.getenv("GCP_REGION", "me-west1")
        ADMIN_DOMAIN: str = os.getenv("ADMIN_DOMAIN", "liatsabag.altostrat.com")

        BILLING_PROJECT_ID: str = os.getenv("BILLING_PROJECT_ID", "gcp-rr-hub-core")
        BILLING_DATASET_ID: str = os.getenv("BILLING_DATASET_ID", "billing")
        BILLING_EXPORT_TABLE: str = os.getenv("BILLING_EXPORT_TABLE", "gcp_billing_export_v1")

        HUB_REGISTRY_DATASET: str = os.getenv("HUB_REGISTRY_DATASET", "hub_registry")
        HUB_TELEMETRY_DATASET: str = os.getenv("HUB_TELEMETRY_DATASET", "hub_telemetry")

        VERTEX_AI_MODEL: str = os.getenv("VERTEX_AI_MODEL", "gemini-3.7-flash")
        VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "me-west1")

        CORS_ORIGINS: List[str] = ["*"]
        API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
