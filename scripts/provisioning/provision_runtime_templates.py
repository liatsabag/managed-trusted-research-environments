"""Provision dedicated VPC networking and Colab Enterprise Runtime Templates across Spoke Projects.

Reads room topology dynamically from scripts/fixtures/fleet_topology.json (Single Source of Truth).
Pure standard library + google.auth / googleapiclient.
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import google.auth
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("provision_runtime_templates")

MACHINE_TYPE = os.getenv("NOTEBOOK_MACHINE_TYPE", "e2-standard-4")
DISK_TYPE = os.getenv("NOTEBOOK_DISK_TYPE", "pd-standard")
DISK_SIZE_GB = os.getenv("NOTEBOOK_DISK_SIZE_GB", "100")


def load_spoke_specs_from_topology(topology_path: Optional[Path] = None) -> Tuple[str, Dict[str, Dict[str, str]]]:
    """Parse dynamic spoke specifications and region from fleet_topology.json."""
    if topology_path is None:
        topology_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topology_path, "r", encoding="utf-8") as f:
        topology = json.load(f)

    region = topology.get("hub_project", {}).get("region", "me-west1")
    spoke_specs: Dict[str, Dict[str, str]] = {}

    for room in topology.get("research_rooms", []):
        room_id = room["room_id"]
        project_id = room["spoke_project_id"]
        short_name = room_id.replace("rr-", "").split("-")[0]
        if short_name == "oncology":
            short_name = "onco"
        elif short_name == "genomics":
            short_name = "genom"
        elif short_name == "neurology":
            short_name = "neuro"

        tpl_id = f"tpl-{short_name}-default"
        vpc_name = f"vpc-spoke-{short_name}"
        subnet_name = f"sb-spoke-{short_name}"
        cidr = f"10.10.{len(spoke_specs) + 1}.0/24"

        spoke_specs[project_id] = {
            "room_id": room_id,
            "room_name": room["room_name"],
            "tpl_id": tpl_id,
            "vpc_name": vpc_name,
            "subnet_name": subnet_name,
            "cidr": cidr,
        }

    return region, spoke_specs


def get_auth_token() -> str:
    """Retrieve OAuth token for Vertex AI REST calls."""
    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not creds.valid:
            import google.auth.transport.requests
            # fallback to subprocess gcloud auth print-access-token
            import subprocess
            res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
            return res.stdout.strip()
        return creds.token or ""
    except Exception:
        import subprocess
        try:
            res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
            return res.stdout.strip()
        except Exception:
            return ""


def rest_request(url: str, method: str = "GET", body: Optional[Dict[str, Any]] = None, token: str = "") -> Tuple[int, Dict[str, Any]]:
    """Helper for authenticated REST requests using standard library urllib."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as he:
        content = he.read().decode("utf-8", errors="ignore")
        return he.code, json.loads(content) if content.startswith("{") else {"error": content}


def wait_compute_op(compute_service: Any, project_id: str, op_name: str, region: Optional[str] = None) -> None:
    """Wait for Compute Engine operation."""
    for _ in range(30):
        time.sleep(2)
        if region:
            op = compute_service.regionOperations().get(project=project_id, region=region, operation=op_name).execute()
        else:
            op = compute_service.globalOperations().get(project=project_id, operation=op_name).execute()
        if op.get("status") == "DONE":
            if "error" in op:
                raise RuntimeError(f"Compute operation {op_name} failed: {op['error']}")
            return


def ensure_spoke_networking(compute: Any, project_id: str, region: str, spec: Dict[str, str], dry_run: bool = False) -> Dict[str, str]:
    """Ensure custom VPC, subnet with Private Google Access, and internal firewall."""
    vpc, subnet, cidr = spec["vpc_name"], spec["subnet_name"], spec["cidr"]
    logger.info("[%s] Configuring VPC '%s' (Subnet: %s, CIDR: %s)...", project_id, vpc, subnet, cidr)
    if dry_run:
        return {"vpc": vpc, "subnet": subnet, "status": "DRY_RUN"}

    try:
        compute.networks().get(project=project_id, network=vpc).execute()
    except Exception:
        vpc_body = {"name": vpc, "autoCreateSubnetworks": False, "routingConfig": {"routingMode": "REGIONAL"}}
        op = compute.networks().insert(project=project_id, body=vpc_body).execute()
        wait_compute_op(compute, project_id, op["name"])

    try:
        compute.subnetworks().get(project=project_id, region=region, subnetwork=subnet).execute()
    except Exception:
        sn_body = {
            "name": subnet,
            "network": f"projects/{project_id}/global/networks/{vpc}",
            "ipCidrRange": cidr,
            "region": region,
            "privateIpGoogleAccess": True,
        }
        op = compute.subnetworks().insert(project=project_id, region=region, body=sn_body).execute()
        wait_compute_op(compute, project_id, op["name"], region=region)

    fw_name = f"{vpc}-allow-internal"
    try:
        compute.firewalls().get(project=project_id, firewall=fw_name).execute()
    except Exception:
        fw_body = {
            "name": fw_name,
            "network": f"projects/{project_id}/global/networks/{vpc}",
            "allowed": [{"IPProtocol": "tcp", "ports": ["0-65535"]}, {"IPProtocol": "udp", "ports": ["0-65535"]}, {"IPProtocol": "icmp"}],
            "sourceRanges": ["10.0.0.0/8"],
        }
        op = compute.firewalls().insert(project=project_id, body=fw_body).execute()
        wait_compute_op(compute, project_id, op["name"])

    return {"vpc": vpc, "subnet": subnet, "firewall": fw_name, "status": "READY"}


def provision_runtime_template(token: str, project_id: str, region: str, spec: Dict[str, str], dry_run: bool = False) -> Dict[str, Any]:
    """Create Colab Enterprise / Vertex AI Notebook Runtime Template in specified region."""
    tpl_id, room_id = spec["tpl_id"], spec["room_id"]
    display_name = f"{spec['room_name']} Colab Enterprise Runtime Template"
    base_url = f"https://{region}-aiplatform.googleapis.com/v1"
    tpl_url = f"{base_url}/projects/{project_id}/locations/{region}/notebookRuntimeTemplates/{tpl_id}"

    logger.info("[%s] Ensuring Notebook Runtime Template '%s'...", project_id, tpl_id)
    if dry_run:
        return {"template_id": tpl_id, "displayName": display_name, "status": "DRY_RUN"}

    code, resp_data = rest_request(tpl_url, token=token)
    if code == 200:
        logger.info("[%s] Runtime template '%s' already exists", project_id, tpl_id)
        return resp_data

    create_url = f"{base_url}/projects/{project_id}/locations/{region}/notebookRuntimeTemplates?notebookRuntimeTemplateId={tpl_id}"
    body = {
        "displayName": display_name,
        "description": f"Colab Enterprise Runtime Template for {room_id}",
        "machineSpec": {"machineType": MACHINE_TYPE},
        "dataPersistentDiskSpec": {"diskType": DISK_TYPE, "diskSizeGb": DISK_SIZE_GB},
        "networkSpec": {
            "network": f"projects/{project_id}/global/networks/{spec['vpc_name']}",
            "subnetwork": f"projects/{project_id}/regions/{region}/subnetworks/{spec['subnet_name']}",
            "enableInternetAccess": True,
        },
    }
    logger.info("[%s] Creating Runtime Template '%s'...", project_id, tpl_id)
    code, resp_data = rest_request(create_url, method="POST", body=body, token=token)
    if code not in (200, 201):
        raise RuntimeError(f"Failed to create template {tpl_id} on {project_id}: HTTP {code} {resp_data}")
    return resp_data


def verify_runtime_templates(region: str, spoke_specs: Dict[str, Dict[str, str]], token: str = "", dry_run: bool = False) -> Dict[str, Any]:
    """Verify all spoke runtime templates exist and are active."""
    results: Dict[str, Any] = {"verified_count": 0, "templates": {}}
    for project_id, spec in spoke_specs.items():
        tpl_id = spec["tpl_id"]
        if dry_run:
            results["templates"][project_id] = {"template_id": tpl_id, "status": "DRY_RUN"}
            continue

        tpl_url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/notebookRuntimeTemplates/{tpl_id}"
        code, data = rest_request(tpl_url, token=token)
        if code != 200:
            raise RuntimeError(f"Verification failed: Template {tpl_id} not found in {project_id} (HTTP {code})")
        results["templates"][project_id] = {"template_id": tpl_id, "status": "ACTIVE"}
        results["verified_count"] += 1
    return results


def provision_all_spoke_runtimes(dry_run: bool = False) -> Dict[str, Any]:
    """Execute complete dynamic networking and runtime template provisioning."""
    region, spoke_specs = load_spoke_specs_from_topology()
    creds, _ = google.auth.default() if not dry_run else (None, None)
    compute = build("compute", "v1", credentials=creds) if not dry_run else None
    token = get_auth_token() if not dry_run else ""

    summary: Dict[str, Any] = {"networking": {}, "templates": {}}
    for project_id, spec in spoke_specs.items():
        summary["networking"][project_id] = ensure_spoke_networking(compute, project_id, region, spec, dry_run=dry_run)
        summary["templates"][project_id] = provision_runtime_template(token, project_id, region, spec, dry_run=dry_run)

    summary["verification"] = verify_runtime_templates(region, spoke_specs, token=token, dry_run=dry_run)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Spoke VPCs and Colab Runtime Templates")
    parser.add_argument("--live", action="store_true", help="Execute against live GCP environment")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifications")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing templates")
    args = parser.parse_args()

    if args.verify_only:
        region, spoke_specs = load_spoke_specs_from_topology()
        token = get_auth_token() if not args.dry_run else ""
        verify_runtime_templates(region, spoke_specs, token=token, dry_run=args.dry_run)
        return 0

    provision_all_spoke_runtimes(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
