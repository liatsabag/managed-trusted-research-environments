"""Storage, Notebooks, Cloud Identity, and IAM verification logic."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import logging
from typing import Any, Dict, List
from scripts.verification.verify_specs import (
    ADMIN_DOMAIN,
    EXPECTED_GROUPS,
    EXPECTED_USERS,
    REGION,
    REQUIRED_SPOKE_ROLES,
    SPOKE_PROJECTS,
)

logger = logging.getLogger("verify_storage_iam")


def verify_cloud_storage(errors: List[str]) -> Dict[str, Any]:
    """Verify Cloud Storage dual-buckets, inbound CSVs, and Colab notebooks across spoke projects."""
    logger.info("=" * 70)
    logger.info("2. LIVE CLOUD STORAGE & NOTEBOOKS VERIFICATION (Region: %s)", REGION)
    logger.info("=" * 70)

    from google.cloud import storage

    gcs_client = storage.Client()
    stats: Dict[str, Any] = {"buckets_found": 0, "blobs_found": 0, "notebooks_found": 0, "details": {}}

    for spoke_proj, spec in SPOKE_PROJECTS.items():
        logger.info("Verifying Storage Buckets in Spoke Project: %s", spoke_proj)
        for bucket_name, expected_blobs in spec["buckets"].items():
            stats["details"][bucket_name] = {"project": spoke_proj, "status": "MISSING", "blobs": {}}
            try:
                bucket = gcs_client.get_bucket(bucket_name)
                stats["buckets_found"] += 1
                stats["details"][bucket_name]["status"] = "EXISTS"
                stats["details"][bucket_name]["location"] = bucket.location
                logger.info("[BUCKET OK] gs://%s (Location: %s, Class: %s)", bucket.name, bucket.location, bucket.storage_class)

                live_blobs = {b.name: b for b in bucket.list_blobs()}
                for blob_name in expected_blobs:
                    if blob_name in live_blobs:
                        blob = live_blobs[blob_name]
                        stats["blobs_found"] += 1
                        if blob_name.endswith(".ipynb"):
                            stats["notebooks_found"] += 1
                        stats["details"][bucket_name]["blobs"][blob_name] = {
                            "size_bytes": blob.size,
                            "content_type": blob.content_type,
                        }
                        logger.info("  - [BLOB OK]  %-45s | Size: %6d bytes | Content-Type: %s", blob.name, blob.size, blob.content_type)
                    else:
                        err = f"CRITICAL: Expected blob '{blob_name}' missing in bucket 'gs://{bucket_name}' (Project: {spoke_proj})."
                        logger.error("  - [MISSING BLOB] %-45s in gs://%s", blob_name, bucket_name)
                        errors.append(err)
            except Exception as exc:
                err = f"CRITICAL: Error accessing bucket 'gs://{bucket_name}' in project '{spoke_proj}': {exc}"
                logger.error(err)
    # Verify Hub Approvals Bucket & Prerequisite Document Trees
    from scripts.verification.verify_specs import EXPECTED_HUB_BUCKETS, HUB_PROJECT_ID
    logger.info("Verifying Regulatory Approvals Bucket in Hub Project: %s", HUB_PROJECT_ID)
    for bkt_name, room_files_map in EXPECTED_HUB_BUCKETS.items():
        stats["details"][bkt_name] = {"project": HUB_PROJECT_ID, "status": "MISSING", "blobs": {}}
        try:
            b = gcs_client.get_bucket(bkt_name)
            stats["buckets_found"] += 1
            stats["details"][bkt_name]["status"] = "EXISTS"
            logger.info("[APPROVALS BUCKET OK] gs://%s (Location: %s)", b.name, b.location)
            live_blobs = {blob.name: blob for blob in b.list_blobs()}
            for room_folder, file_list in room_files_map.items():
                for fname in file_list:
                    expected_blob_path = f"{room_folder}/{fname}"
                    if expected_blob_path in live_blobs:
                        stats["blobs_found"] += 1
                        stats["details"][bkt_name]["blobs"][expected_blob_path] = {"size": live_blobs[expected_blob_path].size}
                        logger.info("  - [APPROVAL DOC OK] %-50s", expected_blob_path)
                    else:
                        err = f"CRITICAL: Missing approval document '{expected_blob_path}' in gs://{bkt_name}"
                        logger.error("  - [MISSING DOC] %s", expected_blob_path)
                        errors.append(err)
        except Exception as exc:
            err = f"CRITICAL: Failed accessing approvals bucket gs://{bkt_name} in {HUB_PROJECT_ID}: {exc}"
            logger.error(err)
            errors.append(err)

    return stats


def verify_cloud_identity_and_iam(errors: List[str]) -> Dict[str, Any]:
    """Verify Cloud Identity users, groups, and Spoke Project IAM role bindings."""
    logger.info("=" * 70)
    logger.info("3. LIVE CLOUD IDENTITY & SPOKE IAM ROLE VERIFICATION (Domain: %s)", ADMIN_DOMAIN)
    logger.info("=" * 70)

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    import google.auth

    stats: Dict[str, Any] = {
        "users_found": 0,
        "groups_found": 0,
        "iam_bindings_verified": 0,
        "details": {"users": {}, "groups": {}, "iam": {}},
    }

    try:
        creds, _ = google.auth.default()
        admin_service = build("admin", "directory_v1", credentials=creds)
        crm_service = build("cloudresourcemanager", "v1", credentials=creds)
    except Exception as exc:
        err = f"CRITICAL: Failed to build Google Cloud API clients: {exc}"
        logger.error(err)
        errors.append(err)
        return stats

    # 1. Verify Groups
    for group_email in EXPECTED_GROUPS:
        try:
            group = admin_service.groups().get(groupKey=group_email).execute()
            stats["groups_found"] += 1
            stats["details"]["groups"][group_email] = {"id": group.get("id"), "name": group.get("name"), "status": "EXISTS"}
            logger.info("[GROUP OK] %-50s | Name: %s", group_email, group.get("name"))
        except HttpError as exc:
            if exc.resp.status == 404:
                err = f"CRITICAL: Cloud Identity group '{group_email}' does not exist."
                logger.error("[MISSING GROUP] %s", group_email)
                errors.append(err)
            else:
                logger.warning("Group check notice for %s: %s", group_email, exc)

    # 2. Verify Users
    for user_email in EXPECTED_USERS:
        try:
            user = admin_service.users().get(userKey=user_email).execute()
            stats["users_found"] += 1
            full_name = user.get("name", {}).get("fullName", "Unknown")
            stats["details"]["users"][user_email] = {"name": full_name, "status": "EXISTS"}
            logger.info("[USER OK]  %-50s | Name: %s", user_email, full_name)
        except HttpError as exc:
            if exc.resp.status == 404:
                err = f"CRITICAL: Cloud Identity user '{user_email}' does not exist."
                logger.error("[MISSING USER] %s", user_email)
                errors.append(err)
            else:
                logger.warning("User check notice for %s: %s", user_email, exc)

    # 3. Verify Spoke Project IAM Role Bindings
    for spoke_proj, spec in SPOKE_PROJECTS.items():
        logger.info("Checking IAM bindings for Spoke Project: %s", spoke_proj)
        group_email = spec["group"]
        group_member = f"group:{group_email}"
        stats["details"]["iam"][spoke_proj] = {}

        try:
            policy = crm_service.projects().getIamPolicy(resource=spoke_proj).execute()
            bindings = policy.get("bindings", [])
            role_map = {b["role"]: b.get("members", []) for b in bindings}

            for role in REQUIRED_SPOKE_ROLES:
                members_for_role = role_map.get(role, [])
                is_group_bound = group_member in members_for_role
                users_bound = [u for u in spec["users"] if f"user:{u}" in members_for_role]

                if is_group_bound:
                    stats["iam_bindings_verified"] += 1
                    stats["details"]["iam"][spoke_proj][role] = {"status": "BOUND", "target": group_member}
                    logger.info("  - [IAM OK]  %-35s -> Bound to %s", role, group_member)
                elif len(users_bound) == len(spec["users"]):
                    stats["iam_bindings_verified"] += 1
                    stats["details"]["iam"][spoke_proj][role] = {"status": "BOUND", "target": "individual_users"}
                    logger.info("  - [IAM OK]  %-35s -> Bound to individual researchers", role)
                else:
                    err = f"CRITICAL: IAM role '{role}' is not granted to '{group_member}' on project '{spoke_proj}'."
                    logger.error("  - [MISSING IAM] %-35s on project %s", role, spoke_proj)
                    errors.append(err)
        except Exception as exc:
            err = f"CRITICAL: Failed to get IAM policy for project '{spoke_proj}': {exc}"
            logger.error(err)
            errors.append(err)

    return stats
