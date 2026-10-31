"""Comprehensive GCP Environment Cleanup Script.

Purges duplicate data, rogue datasets, and misallocated assets across Hub and Spoke projects.
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import os
import sys
from typing import Any, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cleanup_gcp")

HUB_PROJECT = "gcp-rr-hub-core"
SPOKE_PROJECTS = [
    "gcp-rr-spoke-oncology-01",
    "gcp-rr-spoke-genomics-02",
    "gcp-rr-spoke-cardio-03",
    "gcp-rr-spoke-neurology-04",
]
REGION = "me-west1"


def cleanup_bigquery() -> Dict[str, Any]:
    """Clean up rogue BigQuery datasets and truncate duplicated tables."""
    from google.cloud import bigquery

    summary = {
        "datasets_deleted": [],
        "tables_purged": [],
        "errors": [],
    }

    try:
        hub_bq = bigquery.Client(project=HUB_PROJECT, location=REGION)

        # 1. Delete rogue billing dataset in Hub
        rogue_hub_datasets = [
            "billing",
            "spoke_local_oncology",
            "spoke_local_genomics",
            "spoke_local_cardio",
            "spoke_local_neurology",
        ]
        for ds_id in rogue_hub_datasets:
            ds_ref = f"{HUB_PROJECT}.{ds_id}"
            try:
                hub_bq.delete_dataset(ds_ref, delete_contents=True, not_found_ok=True)
                logger.info("Deleted rogue dataset if existed: %s", ds_ref)
                summary["datasets_deleted"].append(ds_ref)
            except Exception as e:
                logger.warning("Error deleting dataset %s: %s", ds_ref, e)
                summary["errors"].append(f"delete_dataset {ds_ref}: {e}")

        # 2. Truncate / delete all tables in hub_registry to purge duplicates
        reg_tables = ["reg_room_packages", "reg_researchers", "reg_research_rooms", "reg_institutes"]
        for tbl in reg_tables:
            tbl_ref = f"{HUB_PROJECT}.hub_registry.{tbl}"
            try:
                hub_bq.delete_table(tbl_ref, not_found_ok=True)
                logger.info("Purged hub_registry table: %s", tbl_ref)
                summary["tables_purged"].append(tbl_ref)
            except Exception as e:
                logger.warning("Error deleting table %s: %s", tbl_ref, e)

        # 3. Truncate / delete all tables in hub_telemetry to purge fake telemetry
        tel_tables = ["ops_audit_logs", "ops_airlock_requests", "ops_regulatory_checklist", "view_billing_export"]
        for tbl in tel_tables:
            tbl_ref = f"{HUB_PROJECT}.hub_telemetry.{tbl}"
            try:
                hub_bq.delete_table(tbl_ref, not_found_ok=True)
                logger.info("Purged hub_telemetry table: %s", tbl_ref)
                summary["tables_purged"].append(tbl_ref)
            except Exception as e:
                logger.warning("Error deleting table %s: %s", tbl_ref, e)

        # 4. Clean spoke local tables to prepare for clean seeding
        spoke_ds_map = {
            "gcp-rr-spoke-oncology-01": ("spoke_local_oncology", ["patient_cohort", "tumor_markers", "treatment_outcomes", "immunotherapy_response"]),
            "gcp-rr-spoke-genomics-02": ("spoke_local_genomics", ["variant_calls", "sample_manifests", "phenotype_mapping"]),
            "gcp-rr-spoke-cardio-03": ("spoke_local_cardio", ["ecg_telemetry_metrics", "lipid_profiles", "patient_registry", "cardiac_events"]),
            "gcp-rr-spoke-neurology-04": ("spoke_local_neurology", ["cognitive_assessments", "mri_volumetric_features", "clinical_trial_registry"]),
        }

        for sp_id, (ds_id, tbl_list) in spoke_ds_map.items():
            try:
                sp_bq = bigquery.Client(project=sp_id, location=REGION)
                for tbl in tbl_list:
                    tbl_ref = f"{sp_id}.{ds_id}.{tbl}"
                    try:
                        sp_bq.delete_table(tbl_ref, not_found_ok=True)
                        logger.info("Purged spoke table: %s", tbl_ref)
                        summary["tables_purged"].append(tbl_ref)
                    except Exception as e:
                        logger.warning("Error deleting spoke table %s: %s", tbl_ref, e)
            except Exception as se:
                logger.warning("Spoke client error for %s: %s", sp_id, se)
    except Exception as exc:
        logger.exception("BigQuery cleanup encountered fatal error: %s", exc)
        summary["errors"].append(str(exc))

    return summary


def cleanup_storage() -> Dict[str, Any]:
    """Delete stray research-room buckets from gcp-billing-export-sink so they can be created in spokes."""
    from google.cloud import storage

    summary = {
        "buckets_deleted": [],
        "errors": [],
    }
    stray_buckets = [
        "rr-oncology-01-inbound",
        "rr-oncology-01-export",
        "rr-genomics-02-inbound",
        "rr-genomics-02-export",
        "rr-cardio-03-inbound",
        "rr-cardio-03-export",
        "rr-neurology-04-inbound",
        "rr-neurology-04-export",
    ]
    try:
        gcs = storage.Client(project="gcp-billing-export-sink")
        for bkt_name in stray_buckets:
            try:
                bucket = gcs.bucket(bkt_name)
                if bucket.exists():
                    # Delete all blobs first
                    blobs = list(bucket.list_blobs())
                    for blob in blobs:
                        blob.delete()
                    bucket.delete(force=True)
                    logger.info("Deleted stray bucket: gs://%s", bkt_name)
                    summary["buckets_deleted"].append(bkt_name)
            except Exception as e:
                logger.warning("Error deleting bucket %s: %s", bkt_name, e)
                summary["errors"].append(f"delete_bucket {bkt_name}: {e}")
    except Exception as exc:
        logger.exception("Storage cleanup error: %s", exc)
        summary["errors"].append(str(exc))

    return summary


def main() -> None:
    """Execute cleanup operations."""
    logger.info(">>> Starting Deep GCP Environment Cleanup...")
    bq_res = cleanup_bigquery()
    st_res = cleanup_storage()
    logger.info("Cleanup completed:")
    print(json.dumps({"bigquery": bq_res, "storage": st_res}, indent=2))


if __name__ == "__main__":
    main()

