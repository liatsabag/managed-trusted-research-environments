"""Legacy verification wrapper - delegates to verify_live_gcp.py."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


from scripts.verification.verify_live_gcp import main

if __name__ == "__main__":
    main()
