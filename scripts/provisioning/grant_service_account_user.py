"""Grant roles/iam.serviceAccountUser to research room groups and users across all spoke projects."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("grant_service_account_user")


def main() -> int:
    topo_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topo_path, "r", encoding="utf-8") as f:
        topology = json.load(f)

    for room in topology.get("research_rooms", []):
        project_id = room["spoke_project_id"]
        group_email = room["cloud_identity_group"]
        researchers = [r["primary_email"] for r in room.get("researchers", [])]

        members = [f"group:{group_email}"] + [f"user:{email}" for email in researchers]
        logger.info("Granting roles/iam.serviceAccountUser on project %s to: %s", project_id, members)

        for member in members:
            cmd = [
                "gcloud", "projects", "add-iam-policy-binding",
                project_id,
                f"--member={member}",
                "--role=roles/iam.serviceAccountUser",
                "--condition=None",
                "--quiet",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                logger.info("  ✓ [OK] Granted roles/iam.serviceAccountUser to %s on %s", member, project_id)
            else:
                logger.warning("  ✗ [FAILED] %s on %s: %s", member, project_id, res.stderr.strip())

    logger.info("All roles/iam.serviceAccountUser grants completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
