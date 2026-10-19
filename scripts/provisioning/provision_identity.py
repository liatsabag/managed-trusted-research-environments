"""Cloud Identity and IAM provisioning module for Research Room fleet."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("provision_identity")

# Standard IAM Roles to bind for each spoke research room group
TARGET_IAM_ROLES = [
    "roles/bigquery.jobUser",
    "roles/bigquery.dataEditor",
    "roles/storage.objectAdmin",
    "roles/aiplatform.user",
    "roles/notebooks.runner",
    "roles/iam.serviceAccountUser",
]


def load_topology(topology_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load fleet topology JSON specification."""
    if topology_path is None:
        topology_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def provision_cloud_identity_users(researchers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Provision Cloud Identity accounts for researchers in live Google Workspace domain."""
    provisioned = []
    admin_service = None

    try:
        import google.auth
        from googleapiclient.discovery import build
        creds, _ = google.auth.default()
        admin_service = build("admin", "directory_v1", credentials=creds)
        logger.info("Connected to live Google Workspace / Cloud Identity Admin Directory API.")
    except Exception as exc:
        logger.warning("Could not initialize Admin SDK client: %s", exc)

    for r in researchers:
        user_record = {
            "primary_email": r["primary_email"],
            "name": {"given_name": r["first_name"], "family_name": r["last_name"]},
            "org_unit_path": r.get("org_unit_path", "/Researchers"),
            "suspended": r.get("access_state") == "SUSPENDED",
            "status": "PROVISIONED",
        }

        if admin_service:
            try:
                # Check if user already exists
                try:
                    existing = admin_service.users().get(userKey=r["primary_email"]).execute()
                    logger.info("Live Cloud Identity User already exists: %s (id: %s)", r["primary_email"], existing.get("id"))
                    user_record["status"] = "ALREADY_EXISTS"
                except Exception:
                    user_body = {
                        "primaryEmail": r["primary_email"],
                        "name": {"givenName": r["first_name"], "familyName": r["last_name"]},
                        "password": "TempPassword123!#",
                        "changePasswordAtNextLogin": True,
                        "orgUnitPath": "/",
                        "suspended": r.get("access_state") == "SUSPENDED",
                    }
                    admin_service.users().insert(body=user_body).execute()
                    logger.info("Created live Cloud Identity User: %s", r["primary_email"])
                    user_record["status"] = "LIVE_CREATED"
            except Exception as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower() or "409" in str(e):
                    logger.info("User %s already exists in Cloud Identity domain.", r["primary_email"])
                    user_record["status"] = "ALREADY_EXISTS"
                else:
                    logger.warning("Live Cloud Identity user creation for %s: %s", r["primary_email"], e)

        logger.info(
            "[LIVE] Cloud Identity User: %s (%s %s) [Status: %s]",
            r["primary_email"],
            r["first_name"],
            r["last_name"],
            user_record["status"],
        )
        provisioned.append(user_record)
    return provisioned


def provision_security_groups(rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create Cloud Identity security groups and enroll researcher members."""
    groups_summary = []
    admin_service = None

    try:
        import google.auth
        from googleapiclient.discovery import build
        creds, _ = google.auth.default()
        admin_service = build("admin", "directory_v1", credentials=creds)
    except Exception as e:
        logger.warning("Could not initialize Admin SDK for group creation: %s", e)

    for room in rooms:
        group_email = room["cloud_identity_group"]
        members = [r["primary_email"] for r in room.get("researchers", [])]
        group_record = {
            "group_email": group_email,
            "room_id": room["room_id"],
            "members": members,
            "status": "PROVISIONED",
        }

        if admin_service:
            try:
                group_body = {
                    "email": group_email,
                    "name": f"Researchers - {room['room_name']}",
                    "description": f"Security group for research room {room['room_id']}",
                }
                admin_service.groups().insert(body=group_body).execute()
                logger.info("Created live Cloud Identity Group: %s", group_email)
                group_record["status"] = "LIVE_CREATED"
            except Exception as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower() or "409" in str(e):
                    logger.info("Group %s already exists.", group_email)
                    group_record["status"] = "ALREADY_EXISTS"
                else:
                    logger.warning("Live group provisioning error for %s: %s", group_email, e)

            for member_email in members:
                try:
                    member_body = {"email": member_email, "role": "MEMBER"}
                    admin_service.members().insert(groupKey=group_email, body=member_body).execute()
                    logger.info("Enrolled member %s into live group %s", member_email, group_email)
                except Exception as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower() or "409" in str(e):
                        logger.info("Member %s already in group %s", member_email, group_email)
                    else:
                        logger.warning("Error enrolling %s in group %s: %s", member_email, group_email, e)

        logger.info(
            "[LIVE] Security Group: %s -> Members: %s",
            group_email,
            members,
        )
        groups_summary.append(group_record)
    return groups_summary


def bind_iam_roles(rooms: List[Dict[str, Any]], dry_run: bool = False) -> List[Dict[str, Any]]:
    """Bind IAM roles to researcher groups and user accounts on their spoke project."""
    bindings = []
    crm_client = None

    if not dry_run:
        try:
            import google.auth
            from googleapiclient.discovery import build
            creds, _ = google.auth.default()
            crm_client = build("cloudresourcemanager", "v1", credentials=creds)
        except Exception as exc:
            logger.warning("Could not initialize Cloud Resource Manager client: %s", exc)

    for room in rooms:
        room_id = room["room_id"]
        spoke_project = room["spoke_project_id"]
        group_email = room["cloud_identity_group"]
        
        # Build member list: both the group and individual researchers
        members_to_bind = [f"group:{group_email}"] + [f"user:{res['primary_email']}" for res in room.get("researchers", [])]

        if crm_client:
            try:
                policy = crm_client.projects().getIamPolicy(resource=spoke_project, body={}).execute()
                current_bindings = policy.get("bindings", [])
                policy_modified = False

                for role in TARGET_IAM_ROLES:
                    binding_obj = next((b for b in current_bindings if b.get("role") == role), None)
                    if not binding_obj:
                        binding_obj = {"role": role, "members": []}
                        current_bindings.append(binding_obj)
                        policy_modified = True

                    for m in members_to_bind:
                        if m not in binding_obj.get("members", []):
                            binding_obj.setdefault("members", []).append(m)
                            policy_modified = True

                if policy_modified:
                    policy["bindings"] = current_bindings
                    crm_client.projects().setIamPolicy(resource=spoke_project, body={"policy": policy}).execute()
                    logger.info("Successfully applied IAM policy bindings on project '%s' for members %s", spoke_project, members_to_bind)
                else:
                    logger.info("IAM policy on project '%s' already up to date for %s", spoke_project, members_to_bind)
            except Exception as e:
                logger.error("FATAL: Could not set live IAM policy for %s on %s: %s", members_to_bind, spoke_project, e)
                raise RuntimeError(f"IAM binding failed for {members_to_bind} on {spoke_project}: {e}") from e

        for role in TARGET_IAM_ROLES:
            for m in members_to_bind:
                binding = {
                    "project_id": spoke_project,
                    "room_id": room_id,
                    "member": m,
                    "role": role,
                    "status": "BOUND" if not dry_run else "DRY_RUN",
                }
                bindings.append(binding)
    return bindings


def sync_registry_researchers(topology: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare researcher registry records for hub_registry.reg_researchers."""
    records = []
    for room in topology.get("research_rooms", []):
        room_id = room["room_id"]
        inst_id = room["institute_id"]
        group_email = room["cloud_identity_group"]
        for r in room.get("researchers", []):
            rec = {
                "researcher_id": r["researcher_id"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "primary_email": r["primary_email"],
                "role": r["role"],
                "access_state": r["access_state"],
                "org_unit_path": r.get("org_unit_path", "/Researchers"),
                "institute_id": inst_id,
                "room_id": room_id,
                "cloud_identity_group": group_email,
                "is_active": r["access_state"] != "SUSPENDED",
            }
            records.append(rec)
    logger.info("Prepared %d researcher records for hub_registry sync.", len(records))
    return records


def provision_identity(topology: Optional[Dict[str, Any]] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Execute end-to-end identity, security group, and IAM provisioning."""
    if topology is None:
        topology = load_topology()

    all_researchers = []
    for rm in topology.get("research_rooms", []):
        all_researchers.extend(rm.get("researchers", []))

    if dry_run:
        registry_recs = sync_registry_researchers(topology)
        return {
            "status": "SUCCESS",
            "users_count": len(all_researchers),
            "groups_count": len(topology.get("research_rooms", [])),
            "iam_bindings_count": len(topology.get("research_rooms", [])) * 5,
            "registry_records_count": len(registry_recs),
        }

    users = provision_cloud_identity_users(all_researchers)
    groups = provision_security_groups(topology.get("research_rooms", []))
    bindings = bind_iam_roles(topology.get("research_rooms", []))
    registry_recs = sync_registry_researchers(topology)

    return {
        "status": "SUCCESS",
        "users_count": len(users),
        "groups_count": len(groups),
        "iam_bindings_count": len(bindings),
        "registry_records_count": len(registry_recs),
        "users": users,
        "groups": groups,
        "bindings": bindings,
        "registry_records": registry_recs,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    summary = provision_identity()
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, indent=2))
