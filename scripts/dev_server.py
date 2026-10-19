"""Unified Local Development Server for GCP Health Data Platform.

Serves the frontend static single-page application and FastAPI backend together
on port 3000, eliminating CORS issues and proxy authentication hurdles.
"""
import logging
import os
import sys
from pathlib import Path

# Ensure root workspace and backend package resolution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from fastapi.staticfiles import StaticFiles
from backend.app.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dev_server")

PORT = int(os.environ.get("PORT", 3000))
FRONTEND_DIR = ROOT_DIR / "frontend"

# Mount static frontend directory at "/" (after API routes are registered)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def main():
    logger.info("=" * 60)
    logger.info("  GCP Health Data Platform — Unified Local Server")
    logger.info("  URL: http://localhost:%d", PORT)
    logger.info("  API Docs: http://localhost:%d/docs", PORT)
    logger.info("  Frontend Path: %s", FRONTEND_DIR)
    logger.info("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
