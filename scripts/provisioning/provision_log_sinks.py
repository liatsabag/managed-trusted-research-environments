"""Provision GCP Cloud Logging Sinks and BigQuery Dataset IAM for Audit Log Streaming."""
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
from typing import Any, Dict, List, Optional
from google.cloud import bigquery

logger = logging.getLogger("provision_log_sinks")

SINK_NAME = "sk-rr-audit-to-hub"
AUDIT_FILTER = 'protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"'


def load_topology(topology_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load fleet topology JSON specification."""
    if topology_path is None:
        topology_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_or_create_sink(project_id: str, destination: str, sink_name: str = SINK_NAME) -> str:
    """Create or update GCP logging sink and return its writer identity."""
    logger.info("Configuring sink '%s' on project '%s' -> %s", sink_name, project_id, destination)
    
    # Check if sink already exists
    describe_cmd = [
        "gcloud", "logging", "sinks", "describe", sink_name,
        f"--project={project_id}",
        "--format=value(writerIdentity)"
    ]
    res = subprocess.run(describe_cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        writer_identity = res.stdout.strip()
        logger.info("Sink '%s' already exists on %s. Writer: %s", sink_name, project_id, writer_identity)
        # Update filter and destination to guarantee accuracy
        update_cmd = [
            "gcloud", "logging", "sinks", "update", sink_name,
            destination,
            f"--log-filter={AUDIT_FILTER}",
            "--use-partitioned-tables",
            f"--project={project_id}"
        ]
        up_res = subprocess.run(update_cmd, capture_output=True, text=True)
        if up_res.returncode != 0:
            logger.warning("Sink update notice: %s", up_res.stderr.strip())
        return writer_identity

    # Create new sink
    create_cmd = [
        "gcloud", "logging", "sinks", "create", sink_name,
        destination,
        f"--log-filter={AUDIT_FILTER}",
        "--use-partitioned-tables",
        f"--project={project_id}"
    ]
    c_res = subprocess.run(create_cmd, capture_output=True, text=True)
    if c_res.returncode != 0:
        raise RuntimeError(f"Failed creating sink on {project_id}: {c_res.stderr.strip()}")

    # Describe to get writer identity
    d_res = subprocess.run(describe_cmd, capture_output=True, text=True)
    if d_res.returncode != 0 or not d_res.stdout.strip():
        raise RuntimeError(f"Failed getting writer identity for {project_id}: {d_res.stderr.strip()}")
    
    writer_identity = d_res.stdout.strip()
    logger.info("Created sink '%s' on %s. Writer identity: %s", sink_name, project_id, writer_identity)
    return writer_identity


def grant_dataset_writer_role(
    hub_project: str,
    dataset_id: str,
    writer_identities: List[str]
) -> List[str]:
    """Grant roles/bigquery.dataEditor on the hub telemetry dataset to all sink writer identities."""
    client = bigquery.Client(project=hub_project)
    dataset = client.get_dataset(f"{hub_project}.{dataset_id}")
    entries = list(dataset.access_entries)
    
    granted_identities = []
    updated = False
    
    for writer_id in writer_identities:
        clean_email = writer_id.replace("serviceAccount:", "").strip()
        already_has_role = any(
            e.entity_id == clean_email and e.role in ("roles/bigquery.dataEditor", "WRITER")
            for e in entries
        )
        if not already_has_role:
            entries.append(
                bigquery.AccessEntry(
                    role="roles/bigquery.dataEditor",
                    entity_type="userByEmail",
                    entity_id=clean_email,
                )
            )
            granted_identities.append(clean_email)
            updated = True
            logger.info("Granted roles/bigquery.dataEditor to %s on %s.%s", clean_email, hub_project, dataset_id)
        else:
            granted_identities.append(clean_email)
            logger.info("Identity %s already has writer role on %s.%s", clean_email, hub_project, dataset_id)

    if updated:
        dataset.access_entries = entries
        client.update_dataset(dataset, ["access_entries"])
        logger.info("Successfully updated BigQuery dataset access control entries.")

    return granted_identities


def provision_log_sinks(topology_path: Optional[Path] = None) -> Dict[str, Any]:
    """Main function to provision log sinks across hub and spoke projects."""
    topology = load_topology(topology_path)
    hub_project = topology.get("hub_project", {}).get("project_id", "gcp-rr-hub-core")
    destination = f"bigquery.googleapis.com/projects/{hub_project}/datasets/hub_telemetry"
    
    target_projects = [hub_project]
    for r in topology.get("research_rooms", []):
        spoke_p = r.get("spoke_project_id")
        if spoke_p and spoke_p not in target_projects:
            target_projects.append(spoke_p)

    results: Dict[str, Any] = {
        "hub_project": hub_project,
        "destination": destination,
        "sinks": {},
        "granted_identities": [],
    }

    writer_ids = []
    for proj in target_projects:
        writer_id = get_or_create_sink(proj, destination, SINK_NAME)
        results["sinks"][proj] = {
            "sink_name": SINK_NAME,
            "destination": destination,
            "writer_identity": writer_id,
            "filter": AUDIT_FILTER,
        }
        writer_ids.append(writer_id)

    granted = grant_dataset_writer_role(hub_project, "hub_telemetry", writer_ids)
    results["granted_identities"] = granted
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    res = provision_log_sinks()
    print(json.dumps(res, indent=2))
