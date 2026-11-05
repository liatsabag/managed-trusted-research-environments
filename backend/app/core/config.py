"""Application configuration module using Pydantic Settings with defensive fallback."""

import json
import os
from functools import lru_cache
from typing import Any, List, Optional, Union

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
        ADMIN_DOMAIN: str = "example-tre.org"

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
        ALLOWED_CORS_ORIGINS: Union[List[str], str] = [
            "http://localhost:8000",
            "http://localhost:8080",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8080",
        ]
        CORS_ORIGINS: Optional[Union[List[str], str]] = None
        API_V1_PREFIX: str = "/api/v1"
        ENVIRONMENT: str = "development"

        # Authentication Configuration
        ENABLE_API_AUTH: bool = False
        API_AUTH_TOKEN: Optional[str] = None

        @property
        def cors_origins(self) -> List[str]:
            raw = self.CORS_ORIGINS if self.CORS_ORIGINS is not None else self.ALLOWED_CORS_ORIGINS
            if isinstance(raw, str):
                cleaned = raw.strip()
                if cleaned.startswith("[") and cleaned.endswith("]"):
                    try:
                        parsed = json.loads(cleaned)
                        if isinstance(parsed, list):
                            return [str(item).strip() for item in parsed if str(item).strip()]
                    except Exception:
                        pass
                return [item.strip() for item in cleaned.split(",") if item.strip()]
            return [str(item).strip() for item in raw]

except ImportError:
    from pydantic import BaseModel

    class Settings(BaseModel):  # type: ignore[no-redef]
        """Fallback configuration settings using pure Pydantic BaseModel and env vars."""

        GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "gcp-rr-hub-core")
        GCP_REGION: str = os.getenv("GCP_REGION", "me-west1")
        ADMIN_DOMAIN: str = os.getenv("ADMIN_DOMAIN", "example-tre.org")

        BILLING_PROJECT_ID: str = os.getenv("BILLING_PROJECT_ID", "gcp-rr-hub-core")
        BILLING_DATASET_ID: str = os.getenv("BILLING_DATASET_ID", "billing")
        BILLING_EXPORT_TABLE: str = os.getenv("BILLING_EXPORT_TABLE", "gcp_billing_export_v1")

        HUB_REGISTRY_DATASET: str = os.getenv("HUB_REGISTRY_DATASET", "hub_registry")
        HUB_TELEMETRY_DATASET: str = os.getenv("HUB_TELEMETRY_DATASET", "hub_telemetry")

        VERTEX_AI_MODEL: str = os.getenv("VERTEX_AI_MODEL", "gemini-3.7-flash")
        VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "me-west1")

        ALLOWED_CORS_ORIGINS: Union[List[str], str] = os.getenv(
            "ALLOWED_CORS_ORIGINS",
            os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:8080,http://localhost:3000,http://127.0.0.1:8000"),
        )
        CORS_ORIGINS: Optional[Union[List[str], str]] = None
        API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

        ENABLE_API_AUTH: bool = os.getenv("ENABLE_API_AUTH", "false").lower() in ("true", "1", "yes")
        API_AUTH_TOKEN: Optional[str] = os.getenv("API_AUTH_TOKEN", None)

        @property
        def cors_origins(self) -> List[str]:
            raw = self.CORS_ORIGINS if self.CORS_ORIGINS is not None else self.ALLOWED_CORS_ORIGINS
            if isinstance(raw, str):
                cleaned = raw.strip()
                if cleaned.startswith("[") and cleaned.endswith("]"):
                    try:
                        parsed = json.loads(cleaned)
                        if isinstance(parsed, list):
                            return [str(item).strip() for item in parsed if str(item).strip()]
                    except Exception:
                        pass
                return [item.strip() for item in cleaned.split(",") if item.strip()]
            return [str(item).strip() for item in raw]


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
