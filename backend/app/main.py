"""Master FastAPI Application for GCP Health Data Platform Central Administrator Portal."""

import sys
import types
from pathlib import Path

# Provide 'backend' package resolution when invoked from inside backend/
if "backend" not in sys.modules:
    _backend_dir = Path(__file__).resolve().parent.parent
    _b = types.ModuleType("backend")
    _b.__path__ = [str(_backend_dir)]
    sys.modules["backend"] = _b
    try:
        import app
        _b.app = app
        sys.modules["backend.app"] = app
    except ImportError:
        pass

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.compliance import router as compliance_router
from backend.app.api.v1.finops import router as finops_router
from backend.app.api.v1.institutes import router as institutes_router
from backend.app.api.v1.rooms import router as rooms_router
from backend.app.api.v1.telemetry import router as telemetry_router
from backend.app.api.v1.resources import router as resources_router
from backend.app.api.v1.airlock import router as airlock_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("health_data_platform_api")

settings = get_settings()

app = FastAPI(
    title="GCP Health Data Platform - Central Administrator Portal API",
    description="Multi-tenant governance, compliance, and research room lifecycle management.",
    version="1.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    """Ensure browsers do not cache dynamic API responses or static SPA assets during testing."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Include API v1 Routers
app.include_router(rooms_router, prefix=f"{settings.API_V1_PREFIX}/rooms", tags=["rooms"])
app.include_router(institutes_router, prefix=f"{settings.API_V1_PREFIX}/institutes", tags=["institutes"])
app.include_router(compliance_router, prefix=f"{settings.API_V1_PREFIX}", tags=["compliance"])
app.include_router(telemetry_router, prefix=f"{settings.API_V1_PREFIX}/telemetry", tags=["telemetry"])
app.include_router(finops_router, prefix=f"{settings.API_V1_PREFIX}", tags=["finops"])
app.include_router(resources_router, prefix=f"{settings.API_V1_PREFIX}", tags=["resources"])
app.include_router(airlock_router, prefix=f"{settings.API_V1_PREFIX}/airlock", tags=["airlock"])
app.include_router(reports_router, prefix=f"{settings.API_V1_PREFIX}/reports", tags=["reports"])




@app.get(f"{settings.API_V1_PREFIX}", tags=["system"])
def api_discovery():
    """API discovery endpoint."""
    return {
        "service": "GCP Health Data Platform Central Administrator Portal API",
        "status": "ONLINE",
        "environment": settings.ENVIRONMENT,
        "region": settings.GCP_REGION,
        "version": "1.0.0",
        "endpoints": {
            "rooms": f"{settings.API_V1_PREFIX}/rooms",
            "institutes": f"{settings.API_V1_PREFIX}/institutes",
            "compliance": f"{settings.API_V1_PREFIX}/compliance",
            "telemetry": f"{settings.API_V1_PREFIX}/telemetry",
            "finops": f"{settings.API_V1_PREFIX}/finops/summary",
            "health": f"{settings.API_V1_PREFIX}/health",
        },
    }


@app.get(f"{settings.API_V1_PREFIX}/health", tags=["system"])
def health():
    """Detailed health check probe."""
    return {
        "status": "HEALTHY",
        "gcp_project_id": settings.GCP_PROJECT_ID,
        "region": settings.GCP_REGION,
        "environment": settings.ENVIRONMENT,
    }


# Mount Static Frontend Single-Page App at Root "/" (Unified Cloud Run deployment)
from fastapi.staticfiles import StaticFiles

_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if _frontend_dir.exists() and (_frontend_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info("Mounted static frontend at root '/' from %s", _frontend_dir)

