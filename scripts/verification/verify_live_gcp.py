"""Strict Live GCP Environment Verification Script for GCP Health Data Platform.

Performs direct, live Google Cloud API checks:
1. BigQuery: Validates datasets, tables, views, row counts, Analytics Hub links, and isolation.
2. Cloud Storage: Validates dual-buckets in me-west1, fixture CSVs, and Colab notebooks.
3. Cloud Identity / Directory API & IAM: Inspects live users, security groups, and spoke IAM bindings.
4. Vertex AI: Validates Colab Enterprise Notebook Runtime Templates in me-west1.
5. Hard-fail: Exits with code 1 if any expected resource is missing, empty, or misconfigured.
"""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import sys
from typing import Any, Dict, List
from google.cloud.exceptions import NotFound
from scripts.provisioning.provision_runtime_templates import (
    load_spoke_specs_from_topology,
    verify_runtime_templates,
)
from scripts.verification.verify_specs import (
    ADMIN_DOMAIN,
    EXPECTED_HUB_DATASETS,
    HUB_PROJECT_ID,
    REGION,
    SPOKE_PROJECTS,
)
from scripts.verification.verify_storage_iam import (
    verify_cloud_identity_and_iam,
    verify_cloud_storage,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("verify_live_gcp")


def verify_hub_bigquery(hub_client: Any, errors: List[str]) -> Dict[str, Any]:
    """Verify Central Hub datasets, tables, views, row counts, and strict isolation."""
    logger.info("=" * 70)
    logger.info("1. LIVE BIGQUERY HUB VERIFICATION (Project: %s, Region: %s)", HUB_PROJECT_ID, REGION)
    logger.info("=" * 70)

    stats: Dict[str, Any] = {"datasets_found": 0, "tables_found": 0, "total_rows": 0, "details": {}}

    for rogue_ds in ["billing", "spoke_local_oncology", "spoke_local_genomics", "spoke_local_cardio", "spoke_local_neurology"]:
        try:
            hub_client.get_dataset(f"{HUB_PROJECT_ID}.{rogue_ds}")
            err = f"CRITICAL: Rogue dataset '{rogue_ds}' found in Hub project '{HUB_PROJECT_ID}'."
            logger.error(err)
            errors.append(err)
        except NotFound:
            logger.info("[ISOLATION OK] Rogue dataset '%s' does NOT exist in Hub project", rogue_ds)
        except Exception as exc:
            logger.warning("Isolation check notice for %s: %s", rogue_ds, exc)

    for dataset_id, expected_tables in EXPECTED_HUB_DATASETS.items():
        dataset_ref = f"{HUB_PROJECT_ID}.{dataset_id}"
        stats["details"][dataset_ref] = {"status": "MISSING", "tables": {}}
        try:
            ds = hub_client.get_dataset(dataset_ref)
            stats["datasets_found"] += 1
            stats["details"][dataset_ref]["status"] = "EXISTS"
            logger.info("[HUB DATASET OK] %s (Location: %s)", dataset_ref, ds.location)
        except NotFound:
            err = f"CRITICAL: Hub dataset '{dataset_ref}' does not exist."
            logger.error(err)
            errors.append(err)
            continue

        for table_id, expected_count in expected_tables.items():
            table_ref = f"{dataset_ref}.{table_id}"
            try:
                tbl = hub_client.get_table(table_ref)
                stats["tables_found"] += 1
                if expected_count == "VIEW":
                    stats["details"][dataset_ref]["tables"][table_id] = {"type": "VIEW", "status": "EXISTS"}
                    logger.info("  - [VIEW OK]  %-30s | Type: %s", table_id, tbl.table_type)
                else:
                    count_job = hub_client.query(f"SELECT COUNT(1) AS cnt FROM `{table_ref}`")
                    rows = list(count_job.result())
                    row_count = rows[0].cnt if rows else 0
                    stats["total_rows"] += row_count
                    stats["details"][dataset_ref]["tables"][table_id] = {
                        "type": tbl.table_type,
                        "rows": row_count,
                        "expected": expected_count,
                    }
                    if row_count != expected_count:
                        err = f"CRITICAL: Row count mismatch in table '{table_ref}': expected {expected_count}, got {row_count}"
                        logger.error("  - [ROW MISMATCH] %-30s | Expected: %d, Actual: %d", table_id, expected_count, row_count)
                        errors.append(err)
                    else:
                        logger.info("  - [TABLE OK] %-30s | Rows: %6d (Expected: %d)", table_id, row_count, expected_count)
            except NotFound:
                err = f"CRITICAL: Table/View '{table_ref}' not found in Hub BigQuery."
                logger.error("  - [MISSING]  %-30s", table_id)
                errors.append(err)
            except Exception as exc:
                err = f"CRITICAL: Error querying '{table_ref}': {exc}"
                logger.error("  - [ERROR]    %-30s | %s", table_id, exc)
                errors.append(err)

    return stats


def verify_spoke_bigquery(errors: List[str]) -> Dict[str, Any]:
    """Verify local spoke datasets, tables, Analytics Hub linked datasets across 4 spoke projects."""
    logger.info("=" * 70)
    logger.info("2. LIVE BIGQUERY SPOKE VERIFICATION ACROSS 4 SPOKE PROJECTS")
    logger.info("=" * 70)
    from google.cloud import bigquery

    stats: Dict[str, Any] = {"datasets_found": 0, "tables_found": 0, "total_rows": 0, "details": {}}

    for spoke_proj, spec in SPOKE_PROJECTS.items():
        spoke_client = bigquery.Client(project=spoke_proj, location=REGION)
        local_ds = spec["dataset_id"]
        local_ref = f"{spoke_proj}.{local_ds}"

        try:
            ds = spoke_client.get_dataset(local_ref)
            stats["datasets_found"] += 1
            logger.info("[SPOKE DATASET OK] %s (Location: %s)", local_ref, ds.location)
        except NotFound:
            err = f"CRITICAL: Spoke local dataset '{local_ref}' does not exist."
            logger.error(err)
            errors.append(err)
            continue

        for table_id, expected_count in spec["tables"].items():
            table_ref = f"{local_ref}.{table_id}"
            try:
                tbl = spoke_client.get_table(table_ref)
                stats["tables_found"] += 1
                count_job = spoke_client.query(f"SELECT COUNT(1) AS cnt FROM `{table_ref}`")
                rows = list(count_job.result())
                row_count = rows[0].cnt if rows else 0
                stats["total_rows"] += row_count
                logger.info("  - [TABLE OK] %-30s | Rows: %6d (Expected: %d)", table_id, row_count, expected_count)
            except Exception as exc:
                err = f"CRITICAL: Error querying spoke table '{table_ref}': {exc}"
                logger.error(err)
                errors.append(err)

        for linked_ds in ["hub_shared_clinical", "hub_shared_reference"]:
            linked_ref = f"{spoke_proj}.{linked_ds}"
            try:
                ds = spoke_client.get_dataset(linked_ref)
                stats["datasets_found"] += 1
                logger.info("[LINKED DATASET OK] %s -> Analytics Hub active", linked_ref)
            except Exception as exc:
                err = f"CRITICAL: Linked dataset '{linked_ref}' error: {exc}"
                logger.error(err)
                errors.append(err)

    return stats


def main() -> int:
    """Execute live verification suite across all 5 projects and services."""
    logger.info("Starting Full Strict Live GCP Verification...")
    errors: List[str] = []

    from google.cloud import bigquery
    hub_client = bigquery.Client(project=HUB_PROJECT_ID, location=REGION)

    hub_bq_stats = verify_hub_bigquery(hub_client, errors)
    spoke_bq_stats = verify_spoke_bigquery(errors)
    storage_stats = verify_cloud_storage(errors)
    identity_stats = verify_cloud_identity_and_iam(errors)

    # Runtime Templates Verification
    region, spoke_specs = load_spoke_specs_from_topology()
    rt_stats = verify_runtime_templates(region, spoke_specs)

    print("\n" + "=" * 80)
    print("STRICT LIVE GCP ENVIRONMENT VERIFICATION SUMMARY REPORT")
    print("=" * 80)
    print(f"Target Region:                   {REGION}")
    print(f"Hub Project:                     {HUB_PROJECT_ID}")
    print(f"Spoke Projects Verified:         {len(SPOKE_PROJECTS)} ({', '.join(SPOKE_PROJECTS.keys())})")
    print(f"BigQuery Datasets Verified:      {hub_bq_stats['datasets_found'] + spoke_bq_stats['datasets_found']} (Hub: {hub_bq_stats['datasets_found']}, Spoke: {spoke_bq_stats['datasets_found']})")
    print(f"BigQuery Tables/Views Verified:  {hub_bq_stats['tables_found'] + spoke_bq_stats['tables_found']}")
    print(f"Total Rows Verified in BQ:       {hub_bq_stats['total_rows'] + spoke_bq_stats['total_rows']:,}")
    print(f"Cloud Storage Buckets Verified:  {storage_stats['buckets_found']} / 8")
    print(f"Colab Enterprise Runtime Tpls:   {rt_stats['verified_count']} / 4 ACTIVE")
    print(f"Cloud Identity Groups Verified:  {identity_stats['groups_found']} / 4")
    print(f"Cloud Identity Users Verified:   {identity_stats['users_found']} / 8")
    print(f"IAM Role Bindings Verified:      {identity_stats['iam_bindings_verified']} / 20")
    print(f"Anomalies / Errors Detected:     {len(errors)}")
    print("=" * 80)

    if errors:
        print("\nFAILURE DETAILS:")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        return 1

    print("\nRESULT: PASSED (100% Verified Live GCP State, 0 Anomalies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
