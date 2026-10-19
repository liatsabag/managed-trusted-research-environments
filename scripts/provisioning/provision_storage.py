"""Cloud Storage dual-bucket, inbound fixture, and regulatory approval provisioning."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import csv
import io
import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.cloud import storage
from scripts.etl.approval_generators import ROOM_APPROVAL_SPECS, build_document_content

logger = logging.getLogger("provision_storage")
random.seed(42)


def load_topology(topology_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load fleet topology JSON specification."""
    if topology_path is None:
        topology_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_inbound_csv_content(filename: str, rows: int) -> str:
    """Generate realistic sanitized CSV records for inbound files."""
    output = io.StringIO()
    writer = csv.writer(output)
    if "demographics" in filename or "registry" in filename:
        writer.writerow(["subject_id", "study_site", "age_group", "gender", "enrollment_quarter", "status"])
        for i in range(rows):
            writer.writerow([f"SUBJ-{1000 + i:04d}", f"SITE-0{1 + (i % 4)}", f"{30 + (i % 50)}-{39 + (i % 50)}",
                             "Female" if i % 2 == 0 else "Male", f"2023-Q{(i % 4) + 1}", "Verified"])
    elif "lab" in filename or "lipid" in filename or "biomarker" in filename or "csf" in filename:
        writer.writerow(["observation_id", "subject_id", "test_code", "measurement_value", "unit", "flag"])
        for i in range(rows):
            writer.writerow([f"OBS-{50000 + i}", f"SUBJ-{1000 + (i % 500):04d}", f"TEST-0{1 + (i % 10)}",
                             round(random.uniform(10.5, 250.0), 2), "mg/dL", "NORMAL" if i % 7 != 0 else "HIGH"])
    elif "tumor" in filename or "variant" in filename or "mutation" in filename:
        writer.writerow(["variant_id", "subject_id", "gene_symbol", "variant_classification", "allele_frequency"])
        for i in range(rows):
            writer.writerow([f"VAR-{90000 + i}", f"SUBJ-{1000 + (i % 500):04d}", f"GENE_{(i % 20) + 1:02d}",
                             "Pathogenic" if i % 5 == 0 else "Benign", round(random.uniform(0.01, 0.49), 4)])
    else:
        writer.writerow(["record_id", "subject_id", "metric_type", "metric_value", "recorded_date"])
        for i in range(rows):
            writer.writerow([f"REC-{10000 + i}", f"SUBJ-{1000 + (i % 500):04d}", "CLINICAL_SCORE",
                             round(random.uniform(0.0, 100.0), 1), "2024-01-15"])
    return output.getvalue()


def generate_quarantine_csv_content(spec: Dict[str, Any]) -> str:
    """Generate candidate egress CSV files with controlled risk markers for airlock review."""
    output = io.StringIO()
    writer = csv.writer(output)
    has_pii = spec.get("has_pii", False)
    has_small_cell = spec.get("has_small_cell_count", False)

    if has_pii:
        writer.writerow(["record_id", "subject_mrn", "patient_full_name", "cohort_group", "mean_outcome", "physician_notes"])
        writer.writerow(["QREC-001", "MRN-984421", "Jane Doe", "Arm-A", 42.5, "Patient showed elevated tumor response."])
        writer.writerow(["QREC-002", "MRN-984422", "John Smith", "Arm-B", 38.1, "Routine follow-up completed."])
    elif has_small_cell:
        writer.writerow(["strata_group", "biomarker_subgroup", "rare_mutation_subgroup_count", "cohort_mean", "ci_lower", "ci_upper"])
        writer.writerow(["Strata-1", "EGFR_T790M", 3, 45.2, 38.1, 52.3])
        writer.writerow(["Strata-2", "KRAS_G12D", 4, 39.8, 32.4, 47.1])
        writer.writerow(["Strata-3", "BRAF_V600E", 142, 51.0, 48.2, 53.8])
    else:
        writer.writerow(["strata_group", "cohort_size", "aggregated_mean", "confidence_interval_95", "compliance_checked"])
        writer.writerow(["Cohort Alpha (Broad Range)", 150, 48.5, "[44.2 - 52.8]", "YES"])
    return output.getvalue()


def provision_approval_documents(
    hub_proj: str,
    region: str,
    staging_dir: Path,
    storage_client: storage.Client,
    summary: Dict[str, Any],
) -> None:
    """Provision gs://gcp-rr-hub-approvals and generate document trees for all 6 rooms."""
    approvals_bkt_name = "gcp-rr-hub-approvals"
    summary["approvals_bucket"] = approvals_bkt_name
    app_dir = staging_dir / approvals_bkt_name
    app_dir.mkdir(parents=True, exist_ok=True)

    bucket = storage_client.bucket(approvals_bkt_name)
    if not bucket.exists():
        storage_client.create_bucket(bucket, project=hub_proj, location=region)
        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        bucket.patch()
        logger.info("Created live approvals bucket: gs://%s in %s", approvals_bkt_name, region)
    else:
        logger.info("Live approvals bucket already exists: gs://%s", approvals_bkt_name)

    for room_id, spec in ROOM_APPROVAL_SPECS.items():
        room_folder = app_dir / room_id
        room_folder.mkdir(parents=True, exist_ok=True)
        for item_type in spec.get("include_items", []):
            fname = f"{item_type.lower()}_approval.txt"
            content = build_document_content(room_id, item_type, spec)
            fpath = room_folder / fname
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            summary["approval_documents_created"] += 1

            blob = bucket.blob(f"{room_id}/{fname}")
            blob.upload_from_string(content, content_type="text/plain")
            logger.info("Uploaded live approval document: gs://%s/%s/%s", approvals_bkt_name, room_id, fname)


def provision_storage(
    topology: Optional[Dict[str, Any]] = None,
    staging_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Provision dual-buckets, inbound files, quarantine candidates, and regulatory approval docs."""
    if topology is None:
        topology = load_topology()
    if staging_dir is None:
        staging_dir = Path(__file__).resolve().parent.parent / "staging" / "storage"

    staging_dir.mkdir(parents=True, exist_ok=True)
    hub_proj = topology.get("hub_project", {}).get("project_id", "gcp-rr-hub-core")
    region = topology.get("hub_project", {}).get("region", "me-west1")

    hub_storage = storage.Client(project=hub_proj)

    summary: Dict[str, Any] = {
        "buckets_provisioned": [],
        "inbound_files_created": 0,
        "quarantine_files_created": 0,
        "approval_documents_created": 0,
        "file_manifest": [],
    }

    # 1. Provision Regulatory Approval Bucket & Documents on Hub
    if not dry_run:
        try:
            provision_approval_documents(hub_proj, region, staging_dir, hub_storage, summary)
        except Exception as e:
            logger.warning("Could not provision remote approval documents (proceeding with local staging): %s", e)
    else:
        # Generate local approval documents in staging
        app_dir = staging_dir / "gcp-rr-hub-approvals"
        app_dir.mkdir(parents=True, exist_ok=True)
        for room_id, spec in ROOM_APPROVAL_SPECS.items():
            room_folder = app_dir / room_id
            room_folder.mkdir(parents=True, exist_ok=True)
            for item_type in spec.get("include_items", []):
                fname = f"{item_type.lower()}_approval.txt"
                content = build_document_content(room_id, item_type, spec)
                fpath = room_folder / fname
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                summary["approval_documents_created"] += 1

    # 2. Provision Dual-Buckets per Research Room in Spoke Projects
    for room in topology.get("research_rooms", []):
        room_id = room["room_id"]
        inbound_bkt = room["inbound_bucket"].replace("gs://", "")
        export_bkt = room["export_bucket"].replace("gs://", "")
        spoke_p = room.get("spoke_project_id", hub_proj)
        summary["buckets_provisioned"].extend([inbound_bkt, export_bkt])

        spoke_storage = storage.Client(project=spoke_p) if not dry_run else None
        if not dry_run and spoke_storage:
            for bkt_name in [inbound_bkt, export_bkt]:
                try:
                    bucket = spoke_storage.bucket(bkt_name)
                    if not bucket.exists():
                        spoke_storage.create_bucket(bucket, project=spoke_p, location=region)
                        bucket.iam_configuration.uniform_bucket_level_access_enabled = True
                        bucket.patch()
                        logger.info("Created spoke bucket: gs://%s in %s (%s)", bkt_name, region, spoke_p)
                except Exception as e:
                    logger.warning("Bucket check/creation skipped for gs://%s: %s", bkt_name, e)

        # Inbound Files
        inbound_dir = staging_dir / inbound_bkt
        inbound_dir.mkdir(parents=True, exist_ok=True)
        for inf in room.get("inbound_files", []):
            fname = inf["filename"]
            row_count = inf.get("rows", 100)
            content = generate_inbound_csv_content(fname, row_count)
            fpath = inbound_dir / fname
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            summary["inbound_files_created"] += 1
            summary["file_manifest"].append({
                "bucket": inbound_bkt, "filename": fname, "type": "INBOUND_SANITIZED", "rows": row_count,
            })
            if not dry_run and spoke_storage:
                try:
                    spoke_storage.bucket(inbound_bkt).blob(fname).upload_from_string(content, content_type="text/csv")
                except Exception as e:
                    logger.warning("Upload skipped for gs://%s/%s: %s", inbound_bkt, fname, e)

        # Quarantine Files
        export_dir = staging_dir / export_bkt
        export_dir.mkdir(parents=True, exist_ok=True)
        for qcand in room.get("quarantine_candidates", []):
            fname = qcand["filename"]
            content = generate_quarantine_csv_content(qcand)
            fpath = export_dir / fname
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            summary["quarantine_files_created"] += 1
            summary["file_manifest"].append({
                "bucket": export_bkt, "filename": fname, "type": "QUARANTINE_CANDIDATE",
                "has_pii": qcand.get("has_pii", False), "has_small_cell": qcand.get("has_small_cell_count", False),
            })
            if not dry_run and spoke_storage:
                try:
                    spoke_storage.bucket(export_bkt).blob(fname).upload_from_string(content, content_type="text/csv")
                except Exception as e:
                    logger.warning("Upload skipped for gs://%s/%s: %s", export_bkt, fname, e)

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    res = provision_storage()
    print(json.dumps({k: v for k, v in res.items() if k != "file_manifest"}, indent=2))
