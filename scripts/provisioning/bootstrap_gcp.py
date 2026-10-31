"""Master centralized CLI runner for GCP Research Room Fleet Live Bootstrap."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.provisioning.provision_bigquery import provision_bigquery
from scripts.provisioning.provision_identity import provision_identity
from scripts.provisioning.provision_notebooks import provision_notebooks
from scripts.provisioning.provision_runtime_templates import provision_all_spoke_runtimes
from scripts.provisioning.provision_storage import provision_storage

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bootstrap_gcp")


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments for modular bootstrap execution."""
    parser = argparse.ArgumentParser(
        description="GCP Health Data Platform Research Room Fleet Live Bootstrap Orchestrator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--all", action="store_true", help="Execute all provisioning steps sequentially")
    parser.add_argument("--hierarchy", action="store_true", help="Ensure folder, projects, billing, and APIs are active")
    parser.add_argument("--identity", action="store_true", help="Provision Cloud Identity users, groups & IAM roles")
    parser.add_argument("--bigquery", action="store_true", help="Deploy BigQuery schemas, datasets, Analytics Hub, and synthetic records")
    parser.add_argument("--storage", action="store_true", help="Provision GCS dual-buckets, inbound files, and egress quarantine")
    parser.add_argument("--notebooks", action="store_true", help="Generate Colab Enterprise / Jupyter notebooks and upload to GCS")
    parser.add_argument("--runtimes", action="store_true", help="Provision VPCs, subnets, and Colab Enterprise Runtime Templates")
    parser.add_argument("--topology", type=str, default=None, help="Path to custom fleet_topology.json")
    return parser.parse_args()


def load_topology(topology_path_str: Optional[str] = None) -> Dict[str, Any]:
    """Load and validate fleet topology JSON."""
    if topology_path_str:
        path = Path(topology_path_str)
    else:
        path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"

    if not path.exists():
        raise FileNotFoundError(f"Fleet topology file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        topology = json.load(f)
    logger.info("Loaded Fleet Topology version %s (%d research rooms)", topology.get("version"), len(topology.get("research_rooms", [])))
    return topology


def ensure_gcp_hierarchy(topology: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure organization folder, Hub and Spoke projects, billing, and APIs exist in live GCP."""
    logger.info(">>> Checking and provisioning live GCP Multi-Project Hierarchy...")
    org_cfg = topology.get("organization", {})
    org_id = org_cfg.get("org_id", "123456789012")
    folder_id = org_cfg.get("folder_id", "123456789012")
    folder_name = org_cfg.get("folder_name", "research-rooms")
    billing_acc = topology.get("billing_configuration", {}).get("billing_account_id", "012345-6789AB-CDEF01")
    billing_acc_name = billing_acc if billing_acc.startswith("billingAccounts/") else f"billingAccounts/{billing_acc}"

    hub_pid = topology.get("hub_project", {}).get("project_id", "gcp-rr-hub-core")
    spoke_pids = [r.get("spoke_project_id") for r in topology.get("research_rooms", []) if r.get("spoke_project_id")]
    all_projects = [hub_pid] + spoke_pids

    hierarchy_status = {
        "folder": folder_name,
        "folder_id": folder_id,
        "projects_verified": [],
        "billing_linked": [],
        "apis_enabled": [],
    }

    try:
        import google.auth
        from googleapiclient.discovery import build

        creds, _ = google.auth.default()
        crm_v1 = build("cloudresourcemanager", "v1", credentials=creds)
        cloudbilling = build("cloudbilling", "v1", credentials=creds)
        serviceusage = build("serviceusage", "v1", credentials=creds)

        parent_dict = {"type": "folder", "id": folder_id} if folder_id else {"type": "organization", "id": org_id}
        for pid in all_projects:
            try:
                crm_v1.projects().get(projectId=pid).execute()
                hierarchy_status["projects_verified"].append(pid)
            except Exception:
                try:
                    crm_v1.projects().create(body={"projectId": pid, "name": pid, "parent": parent_dict}).execute()
                    hierarchy_status["projects_verified"].append(pid)
                    time.sleep(2)
                except Exception as ce:
                    logger.warning("Project creation check for %s: %s", pid, ce)

            # Link Billing
            try:
                cloudbilling.projects().updateBillingInfo(
                    name=f"projects/{pid}",
                    body={"billingAccountName": billing_acc_name, "billingEnabled": True},
                ).execute()
                hierarchy_status["billing_linked"].append(pid)
            except Exception as be:
                logger.warning("Billing linkage notice for %s: %s", pid, be)

            # Enable Required APIs
            required_services = [
                "compute.googleapis.com",
                "bigquery.googleapis.com",
                "analyticshub.googleapis.com",
                "storage.googleapis.com",
                "aiplatform.googleapis.com",
                "logging.googleapis.com",
                "notebooks.googleapis.com",
            ]
            try:
                serviceusage.services().batchEnable(
                    parent=f"projects/{pid}",
                    body={"serviceIds": required_services},
                ).execute()
                hierarchy_status["apis_enabled"].append(pid)
            except Exception as se:
                logger.warning("Service enablement notice for %s: %s", pid, se)

    except Exception as exc:
        logger.warning("Hierarchy check encountered: %s", exc)

    return hierarchy_status


def run_bootstrap(
    run_all: bool = True,
    run_hier: bool = False,
    run_ident: bool = False,
    run_bq: bool = False,
    run_gcs: bool = False,
    run_nb: bool = False,
    run_rt: bool = False,
    dry_run: bool = False,
    topology_path_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrate modular live provisioning steps."""
    topology = load_topology(topology_path_str)
    execution_summary: Dict[str, Any] = {
        "status": "COMPLETED",
        "modules_executed": [],
        "details": {},
    }

    execute_all = run_all or (not run_hier and not run_ident and not run_bq and not run_gcs and not run_nb and not run_rt)

    # 0. Hierarchy
    if (execute_all or run_hier) and not dry_run:
        logger.info(">>> Step 0/5: Live GCP Multi-Project Hierarchy...")
        execution_summary["details"]["hierarchy"] = ensure_gcp_hierarchy(topology)
        execution_summary["modules_executed"].append("hierarchy")

    # 1. Identity & IAM
    if execute_all or run_ident:
        logger.info(">>> Step 1/5: Executing Identity & IAM Provisioning...")
        ident_res = provision_identity(topology=topology, dry_run=dry_run)
        execution_summary["modules_executed"].append("identity")
        execution_summary["details"]["identity"] = {
            "users_count": ident_res["users_count"],
            "groups_count": ident_res["groups_count"],
            "iam_bindings_count": ident_res["iam_bindings_count"],
            "registry_records_count": ident_res["registry_records_count"],
        }

    # 2. BigQuery & Analytics Hub
    if execute_all or run_bq:
        logger.info(">>> Step 2/5: Executing BigQuery Datasets & Analytics Hub Provisioning...")
        bq_res = provision_bigquery(topology=topology, dry_run=dry_run)
        execution_summary["modules_executed"].append("bigquery")
        execution_summary["details"]["bigquery"] = {
            "datasets_count": len(bq_res["datasets"]),
            "total_rows_generated": bq_res["total_rows_generated"],
            "datasets": {k: len(v) for k, v in bq_res["datasets"].items()},
            "analytics_hub": bq_res.get("analytics_hub"),
        }

    # 3. Storage Dual-Buckets
    if execute_all or run_gcs:
        logger.info(">>> Step 3/5: Executing Cloud Storage Dual-Bucket Provisioning...")
        gcs_res = provision_storage(topology=topology, dry_run=dry_run)
        execution_summary["modules_executed"].append("storage")
        execution_summary["details"]["storage"] = {
            "buckets_provisioned": len(gcs_res["buckets_provisioned"]),
            "inbound_files_created": gcs_res["inbound_files_created"],
            "quarantine_files_created": gcs_res["quarantine_files_created"],
        }

    # 4. Notebooks
    if execute_all or run_nb:
        logger.info(">>> Step 4/5: Executing Colab Enterprise Notebook Provisioning...")
        nb_res = provision_notebooks(topology=topology, dry_run=dry_run)
        execution_summary["modules_executed"].append("notebooks")
        execution_summary["details"]["notebooks"] = {
            "notebooks_created": nb_res["notebooks_created"],
            "notebooks_uploaded": nb_res.get("notebooks_uploaded", 0),
            "room_notebooks": {k: len(v) for k, v in nb_res["room_notebooks"].items()},
        }

    # 5. VPC Networking & Runtime Templates
    if execute_all or run_rt:
        logger.info(">>> Step 5/5: Executing VPC & Colab Runtime Template Provisioning...")
        rt_res = provision_all_spoke_runtimes(dry_run=dry_run)
        execution_summary["modules_executed"].append("runtimes")
        execution_summary["details"]["runtimes"] = {
            "templates_verified": rt_res.get("verification", {}).get("verified_count", 0),
        }

    logger.info("======================================================================")
    logger.info("GCP LIVE FLEET BOOTSTRAP EXECUTION SUMMARY:")
    logger.info(json.dumps(execution_summary, indent=2, default=str))
    logger.info("======================================================================")
    return execution_summary


def main() -> None:
    """CLI entry point."""
    args = parse_arguments()
    try:
        run_bootstrap(
            run_all=args.all,
            run_hier=args.hierarchy,
            run_ident=args.identity,
            run_bq=args.bigquery,
            run_gcs=args.storage,
            run_nb=args.notebooks,
            run_rt=args.runtimes,
            topology_path_str=args.topology,
        )
    except Exception as exc:
        logger.exception("Bootstrap execution encountered a critical error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
