"""Root entrypoint for Cloud Run and local execution."""

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, reload=False)
