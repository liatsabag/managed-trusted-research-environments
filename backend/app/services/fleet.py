"""Fleet Governance and Research Room lifecycle management service using live BigQuery and IAM."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set

from google.cloud import bigquery
from googleapiclient import discovery
import google.auth

from backend.app.core.cache import cached_endpoint, cache
from backend.app.core.config import get_settings
from backend.app.models.rooms import (
    AddResearcherResponse,
    DUAComplianceStatus,
    DowngradeRequest,
    InstituteSummary,
    ResearcherMember,
    ResearchRoomDetail,
    ResearchRoomSummary,
    RoomActionResponse,
    RoomPackageItem,
)

logger = logging.getLogger("fleet_governance")

EDITOR_ROLES: Set[str] = {"roles/bigquery.dataEditor", "roles/storage.objectAdmin", "roles/aiplatform.user", "roles/notebooks.runner"}
VIEWER_ROLES: Set[str] = {"roles/bigquery.dataViewer", "roles/storage.objectViewer"}
MANAGED_ROLES: Set[str] = EDITOR_ROLES | VIEWER_ROLES


class FleetGovernanceService:
    """Service managing Research Room fleet registry, DUA compliance, and IAM governance via BigQuery."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._bq_client: Optional[bigquery.Client] = None
        self._crm_client: Optional[Any] = None

    @property
    def bq_client(self) -> bigquery.Client:
        if self._bq_client is None:
            self._bq_client = bigquery.Client(
                project=self.settings.GCP_PROJECT_ID,
                location=self.settings.GCP_REGION,
            )
        return self._bq_client

    @property
    def crm_client(self) -> Any:
        if self._crm_client is None:
            credentials, _ = google.auth.default()
            self._crm_client = discovery.build("cloudresourcemanager", "v1", credentials=credentials)
        return self._crm_client

    def _evaluate_dua_compliance(
        self,
        helsinki_expiry: Optional[Any],
        dua_expiry: Optional[Any],
        status: str,
    ) -> DUAComplianceStatus:
        """Evaluate Helsinki IRB and DUA expiration status and countdowns."""
        today = date.today()
        h_str = helsinki_expiry.isoformat() if isinstance(helsinki_expiry, date) else str(helsinki_expiry) if helsinki_expiry else None
        d_str = dua_expiry.isoformat() if isinstance(dua_expiry, date) else str(dua_expiry) if dua_expiry else None
        h_days = (date.fromisoformat(h_str) - today).days if h_str else None
        d_days = (date.fromisoformat(d_str) - today).days if d_str else None
        is_h_valid = h_days >= 0 if h_days is not None else True
        is_d_valid = d_days >= 0 if d_days is not None else True

        if status in ("SOFT_DOWNGRADED", "SUSPENDED") or not is_h_valid or not is_d_valid:
            level = "EXPIRED" if (not is_h_valid or not is_d_valid) else "NON_COMPLIANT"
            requires_action = True
            notes = "Compliance action required: ethics/DUA expiration or downgrade active."
        elif (h_days is not None and h_days <= 30) or (d_days is not None and d_days <= 30):
            level = "WARNING"
            requires_action = True
            notes = "Approaching expiration within 30 days."
        else:
            level = "COMPLIANT"
            requires_action = False
            notes = "All ethics and data use agreements fully active."

        return DUAComplianceStatus(
            helsinki_expiry_date=h_str,
            dua_expiry_date=d_str,
            helsinki_days_remaining=h_days,
            dua_days_remaining=d_days,
            is_helsinki_valid=is_h_valid,
            is_dua_valid=is_d_valid,
            compliance_level=level,
            requires_action=requires_action,
            notes=notes,
        )

    @cached_endpoint(ttl_seconds=45, key_prefix="fleet_rooms")
    def get_rooms(self) -> List[ResearchRoomSummary]:
        """List all research rooms from BigQuery with compliance metrics, lead researcher, cost and activity."""
        ds = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}"
        tel_ds = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}"
        query = f"""
            WITH room_costs AS (
                SELECT project_id, SUM(cost) AS total_project_cost
                FROM `{tel_ds}.view_billing_export`
                GROUP BY project_id
            ),
            room_activity AS (
                SELECT room_id, MAX(timestamp) AS last_activity_timestamp
                FROM `{tel_ds}.ops_audit_events_curated`
                WHERE room_id IS NOT NULL AND room_id != ''
                  AND (
                      principal_email IN (SELECT primary_email FROM `{ds}.reg_researchers` WHERE is_active = TRUE)
                      OR (principal_email NOT LIKE '%.gserviceaccount.com' AND principal_email NOT LIKE 'admin@%')
                  )
                GROUP BY room_id
            )
            SELECT r.room_id, r.room_name, r.institute_id, i.name AS institute_name,
                   r.spoke_project_id, r.status, r.helsinki_expiry_date, r.dua_expiry_date,
                   r.inbound_bucket, r.export_bucket, r.cloud_identity_group, r.tables_count,
                   r.created_at, r.lead_researcher_id, COALESCE(r.budget_limit_usd, 5000.0) AS budget_limit_usd,
                   COALESCE(res.researcher_count, 0) AS researcher_count,
                   CONCAT(lead_res.first_name, ' ', lead_res.last_name) AS lead_researcher,
                   lead_res.primary_email AS lead_researcher_email,
                   COALESCE(costs.total_project_cost, 0.0) AS total_cost,
                   act.last_activity_timestamp AS last_activity_at
            FROM `{ds}.reg_research_rooms` r
            LEFT JOIN `{ds}.reg_institutes` i ON r.institute_id = i.institute_id
            LEFT JOIN (SELECT room_id, COUNT(*) AS researcher_count FROM `{ds}.reg_researchers` WHERE is_active = TRUE GROUP BY room_id) res ON r.room_id = res.room_id
            LEFT JOIN `{ds}.reg_researchers` lead_res ON (r.lead_researcher_id = lead_res.researcher_id OR r.lead_researcher_email = lead_res.primary_email)
            LEFT JOIN room_costs costs ON r.spoke_project_id = costs.project_id
            LEFT JOIN room_activity act ON r.room_id = act.room_id
            ORDER BY r.room_id
        """
        rows = list(self.bq_client.query(query).result())
        pkg_rows = list(self.bq_client.query(f"SELECT room_id, package_name FROM `{ds}.reg_room_packages` ORDER BY package_name").result())
        room_pkgs: Dict[str, List[str]] = {}
        for pr in pkg_rows:
            room_pkgs.setdefault(pr["room_id"], []).append(pr["package_name"])

        summaries: List[ResearchRoomSummary] = []
        for row in rows:
            pkgs = room_pkgs.get(row["room_id"], [])
            dep_date = row["created_at"].strftime("%Y-%m-%d") if row.get("created_at") else None
            last_act = row["last_activity_at"].isoformat() if row.get("last_activity_at") else None
            summaries.append(
                ResearchRoomSummary(
                    room_id=row["room_id"], room_name=row["room_name"], institute_id=row["institute_id"],
                    institute_name=row["institute_name"], lead_researcher_id=row.get("lead_researcher_id"),
                    lead_researcher=row.get("lead_researcher") or "Principal Investigator",
                    lead_researcher_email=row.get("lead_researcher_email"), deployment_date=dep_date,
                    spoke_project_id=row["spoke_project_id"], status=row["status"],
                    compliance=self._evaluate_dua_compliance(row["helsinki_expiry_date"], row["dua_expiry_date"], row["status"]),
                    researcher_count=row["researcher_count"], table_count=row["tables_count"] or 0,
                    packages_count=len(pkgs), active_packages=pkgs[:5], total_cost=float(row["total_cost"] or 0.0),
                    budget_limit_usd=float(row["budget_limit_usd"] or 5000.0),
                    last_activity_at=last_act,
                    health_status="DOWNGRADED" if row["status"] in ("SOFT_DOWNGRADED", "SUSPENDED") else "HEALTHY",
                )
            )
        return summaries

    def list_rooms(self) -> List[ResearchRoomSummary]:
        return self.get_rooms()

    @cached_endpoint(ttl_seconds=45, key_prefix="fleet_room_detail")
    def get_room(self, room_id: str) -> Optional[ResearchRoomDetail]:
        """Get detailed view of a specific research room from BigQuery."""
        ds = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}"
        tel_ds = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}"
        query = f"""
            WITH room_costs AS (
                SELECT project_id, SUM(cost) + IFNULL(SUM((SELECT SUM(c.amount) FROM UNNEST(credits) c)), 0) AS total_project_cost
                FROM `{tel_ds}.view_billing_export`
                GROUP BY project_id
            )
            SELECT r.room_id, r.room_name, r.institute_id, i.name AS institute_name,
                   r.spoke_project_id, r.status, r.helsinki_expiry_date, r.dua_expiry_date,
                   r.inbound_bucket, r.export_bucket, r.cloud_identity_group, r.tables_count,
                   r.created_at, r.lead_researcher_id, COALESCE(r.budget_limit_usd, 5000.0) AS budget_limit_usd,
                   CONCAT(lead_res.first_name, ' ', lead_res.last_name) AS lead_researcher_name,
                   lead_res.primary_email AS lead_researcher_email,
                   COALESCE(costs.total_project_cost, 0.0) AS total_cost
            FROM `{ds}.reg_research_rooms` r
            LEFT JOIN `{ds}.reg_institutes` i ON r.institute_id = i.institute_id
            LEFT JOIN `{ds}.reg_researchers` lead_res ON (r.lead_researcher_id = lead_res.researcher_id OR r.lead_researcher_email = lead_res.primary_email)
            LEFT JOIN room_costs costs ON r.spoke_project_id = costs.project_id
            WHERE r.room_id = @room_id
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("room_id", "STRING", room_id)])
        rows = list(self.bq_client.query(query, job_config=job_config).result())
        if not rows:
            return None
        r = rows[0]

        res_query = f"""
            WITH res_activity AS (
                SELECT principal_email, MAX(timestamp) AS last_act
                FROM `{tel_ds}.ops_audit_events_curated`
                WHERE room_id = @room_id
                GROUP BY principal_email
            )
            SELECT res.*, act.last_act
            FROM `{ds}.reg_researchers` res
            LEFT JOIN res_activity act ON res.primary_email = act.principal_email
            WHERE res.room_id = @room_id
            ORDER BY res.researcher_id
        """
        researchers = [
            ResearcherMember(
                researcher_id=res["researcher_id"],
                first_name=res["first_name"],
                last_name=res["last_name"],
                primary_email=res["primary_email"],
                role=res["role"],
                access_state=res["access_state"],
                org_unit_path=res["org_unit_path"],
                is_active=bool(res["is_active"]),
                institute_id=res["institute_id"],
                room_id=res["room_id"],
                last_activity_at=res["last_act"].isoformat() if res.get("last_act") else None,
            )
            for res in self.bq_client.query(res_query, job_config=job_config).result()
        ]

        pkg_query = f"SELECT * FROM `{ds}.reg_room_packages` WHERE room_id = @room_id ORDER BY package_name"
        packages = [
            RoomPackageItem(
                room_id=p["room_id"],
                runtime_id=p["runtime_id"],
                package_name=p["package_name"],
                package_version=p["package_version"],
                installed_at=p["installed_at"].isoformat() if p["installed_at"] else None,
            )
            for p in self.bq_client.query(pkg_query, job_config=job_config).result()
        ]

        short = room_id.replace("rr-", "").split("-")[0]
        vpc_name, subnet_name, tpl_id = f"vpc-spoke-{room_id.replace('rr-', '')}", f"sb-spoke-{room_id.replace('rr-', '')}", f"tpl-{short}-default"
        dep_date = r["created_at"].date().isoformat() if r.get("created_at") else None
        return ResearchRoomDetail(
            room_id=room_id, room_name=r["room_name"], institute_id=r["institute_id"],
            institute_name=r["institute_name"], lead_researcher_id=r.get("lead_researcher_id"),
            lead_researcher=r.get("lead_researcher_name") or "Principal Investigator",
            lead_researcher_email=r.get("lead_researcher_email"), deployment_date=dep_date,
            spoke_project_id=r["spoke_project_id"], status=r["status"],
            compliance=self._evaluate_dua_compliance(r["helsinki_expiry_date"], r["dua_expiry_date"], r["status"]),
            budget_limit_usd=float(r["budget_limit_usd"] or 5000.0),
            total_cost=float(r["total_cost"] or 0.0),
            inbound_bucket=r["inbound_bucket"], export_bucket=r["export_bucket"],
            cloud_identity_group=r["cloud_identity_group"], vpc_name=vpc_name, subnet_name=subnet_name,
            template_id=tpl_id, template_name=f"{r['room_name']} Colab Enterprise Runtime Template",
            shared_dataset_subscriptions=["hub_clinical_omop", "hub_imaging_dicom"],
            local_dataset_id=f"spoke_local_{short}", tables_count=r["tables_count"] or len(packages),
            researchers=researchers, packages=packages,
            health_status="DOWNGRADED" if r["status"] in ("SOFT_DOWNGRADED", "SUSPENDED") else "HEALTHY",
            health_details={
                "vpc_network": {"name": vpc_name, "status": "ACTIVE", "private_google_access": True},
                "subnetwork": {"name": subnet_name, "status": "ACTIVE", "region": self.settings.GCP_REGION},
                "runtime_template": {"id": tpl_id, "status": "READY", "machine_type": "e2-standard-4"},
                "storage_inbound": {"uri": r["inbound_bucket"], "status": "ACCESSIBLE"},
                "storage_export": {"uri": r["export_bucket"], "status": "ACCESSIBLE"},
            },
        )

    def get_room_packages(self, room_id: str) -> Optional[Dict[str, Any]]:
        detail = self.get_room(room_id)
        if not detail:
            return None
        return {
            "room_id": room_id,
            "shared_dataset_subscriptions": detail.shared_dataset_subscriptions,
            "local_dataset": {"dataset_id": detail.local_dataset_id, "tables_count": detail.tables_count},
            "notebooks": ["exploratory_analysis.ipynb", "cohort_selection.ipynb"],
            "installed_packages": [p.model_dump() for p in detail.packages],
            "inbound_files": [],
        }

    @cached_endpoint(ttl_seconds=60, key_prefix="fleet_institutes")
    def get_institutes(self) -> List[InstituteSummary]:
        ds = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}"
        inst_rows = list(self.bq_client.query(f"SELECT institute_id, name, country, contact_email FROM `{ds}.reg_institutes` ORDER BY institute_id").result())
        room_rows = list(self.bq_client.query(f"SELECT room_id, institute_id FROM `{ds}.reg_research_rooms`").result())
        rooms_by_inst: Dict[str, List[str]] = {}
        for r in room_rows:
            rooms_by_inst.setdefault(r["institute_id"], []).append(r["room_id"])
        return [
            InstituteSummary(
                institute_id=row["institute_id"], name=row["name"], contact_email=row["contact_email"],
                country=row.get("country", "USA"), room_count=len(rooms_by_inst.get(row["institute_id"], [])),
                rooms=rooms_by_inst.get(row["institute_id"], [])
            ) for row in inst_rows
        ]

    def list_institutes(self) -> List[InstituteSummary]:
        return self.get_institutes()

    def get_institute(self, institute_id: str) -> Optional[InstituteSummary]:
        for inst in self.get_institutes():
            if inst.institute_id == institute_id:
                return inst
        return None

    def _apply_spoke_iam_mutation(self, spoke_project_id: str, group_email: str, new_status: str) -> None:
        """Apply live IAM policy bindings on spoke project according to room status."""
        try:
            policy = self.crm_client.projects().getIamPolicy(resource=spoke_project_id, body={}).execute()
            group_member = f"group:{group_email}" if not group_email.startswith("group:") else group_email
            bindings = policy.get("bindings", [])
            for b in bindings:
                if b.get("role") in MANAGED_ROLES:
                    b["members"] = [m for m in b.get("members", []) if m != group_member]

            target_roles = EDITOR_ROLES if new_status == "ACTIVE" else (VIEWER_ROLES if new_status == "SOFT_DOWNGRADED" else set())
            for role in target_roles:
                for b in bindings:
                    if b.get("role") == role:
                        if group_member not in b["members"]:
                            b["members"].append(group_member)
                        break
                else:
                    bindings.append({"role": role, "members": [group_member]})

            policy["bindings"] = [b for b in bindings if b.get("members")]
            self.crm_client.projects().setIamPolicy(resource=spoke_project_id, body={"policy": policy}).execute()
            logger.info("Updated IAM policy on %s for %s to %s", spoke_project_id, group_member, new_status)
        except Exception as e:
            logger.error("Failed to mutate IAM on spoke %s: %s", spoke_project_id, e)
            raise

    def update_room_status(self, room_id: str, new_status: str, reason: Optional[str] = None) -> Optional[RoomActionResponse]:
        """Update room status in BigQuery and mutate spoke project IAM policy."""
        if new_status not in {"ACTIVE", "SOFT_DOWNGRADED", "SUSPENDED"}:
            raise ValueError(f"Invalid status '{new_status}'")
        ds = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}"
        job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("room_id", "STRING", room_id)])
        rows = list(self.bq_client.query(f"SELECT * FROM `{ds}.reg_research_rooms` WHERE room_id = @room_id", job_config=job_config).result())
        if not rows:
            return None
        current = rows[0]
        prev_status = current["status"]

        # Update BigQuery room status
        up_cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("new_status", "STRING", new_status),
            bigquery.ScalarQueryParameter("room_id", "STRING", room_id),
        ])
        self.bq_client.query(f"UPDATE `{ds}.reg_research_rooms` SET status = @new_status WHERE room_id = @room_id", job_config=up_cfg).result()

        # Update Researcher access states
        res_access = "ACTIVE" if new_status == "ACTIVE" else ("DOWNGRADED_READONLY" if new_status == "SOFT_DOWNGRADED" else "SUSPENDED")
        res_cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("access_state", "STRING", res_access),
            bigquery.ScalarQueryParameter("room_id", "STRING", room_id),
        ])
        self.bq_client.query(f"UPDATE `{ds}.reg_researchers` SET access_state = @access_state WHERE room_id = @room_id", job_config=res_cfg).result()
        self._apply_spoke_iam_mutation(current["spoke_project_id"], current["cloud_identity_group"], new_status)

        # Invalidate in-memory cache to reflect immediately across all tabs
        cache.invalidate()

        aff_rows = list(self.bq_client.query(f"SELECT primary_email FROM `{ds}.reg_researchers` WHERE room_id = @room_id", job_config=job_config).result())
        action_name = "downgrade" if new_status == "SOFT_DOWNGRADED" else ("reactivate" if new_status == "ACTIVE" else "suspend")
        return RoomActionResponse(
            room_id=room_id,
            action=action_name,
            previous_status=prev_status,
            new_status=new_status,
            affected_researchers=[r["primary_email"] for r in aff_rows],
            success=True,
            message=f"Research room '{room_id}' status updated to {new_status}. {reason or ''}".strip(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def downgrade_room(self, room_id: str, request: Optional[DowngradeRequest] = None) -> Optional[RoomActionResponse]:
        return self.update_room_status(room_id, "SOFT_DOWNGRADED", reason=request.reason if request else "Compliance enforcement")

    def reactivate_room(self, room_id: str) -> Optional[RoomActionResponse]:
        return self.update_room_status(room_id, "ACTIVE", reason="Compliance renewal / reactivation")

    def add_researcher_stub(self, room_id: str, researcher_email: str, role: str = "Researcher") -> AddResearcherResponse:
        logger.info("Stub provisioning researcher %s (%s) for room %s", researcher_email, role, room_id)
        return AddResearcherResponse(
            room_id=room_id,
            researcher_email=researcher_email,
            role=role,
            status="PROVISIONED_STUB",
            message=f"Researcher {researcher_email} provisioned stub for room {room_id}.",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


_fleet_service_instance: Optional[FleetGovernanceService] = None


def get_fleet_service() -> FleetGovernanceService:
    global _fleet_service_instance
    if _fleet_service_instance is None:
        _fleet_service_instance = FleetGovernanceService()
    return _fleet_service_instance
