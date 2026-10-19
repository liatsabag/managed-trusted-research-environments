import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import bigquery, storage

from backend.app.core.cache import cached_endpoint, cache
from backend.app.core.config import get_settings
from backend.app.models.telemetry import (
    AIUsageMetricItem,
    AuditLogEvent,
    DailyComputeMetricItem,
    FleetTelemetryOverview,
    MonthlyUsageRollupItem,
    NotebookSessionItem,
    QueryJobItem,
    RoomActivitySummary,
    RoomAssetInventory,
    TelemetrySyncResponse,
)

logger = logging.getLogger(__name__)


class TelemetryService:
    """Service for querying telemetry, BigQuery job logs, audit logs, and inventory."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.bq_client = bigquery.Client(project=self.settings.GCP_PROJECT_ID, location=self.settings.GCP_REGION)
        self.gcs_client = storage.Client(project=self.settings.GCP_PROJECT_ID)

    def _get_active_spoke_projects(self, room_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch active spoke projects from hub_registry.reg_research_rooms."""
        query = f"""
            SELECT room_id, room_name, spoke_project_id, institute_id, inbound_bucket, export_bucket
            FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}.reg_research_rooms`
            WHERE (status = 'ACTIVE' OR status IS NOT NULL)
        """
        params: List[bigquery.ScalarQueryParameter] = []
        if room_id:
            query += " AND room_id = @room_id"
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id.strip()))

        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = self.bq_client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]

    @cached_endpoint(ttl_seconds=45, key_prefix="telemetry_overview")
    def get_fleet_overview(self) -> FleetTelemetryOverview:
        """Calculate fleet-wide telemetry overview across all research rooms."""
        rooms = self._get_active_spoke_projects()
        if not rooms:
            return FleetTelemetryOverview()

        unions = [
            f"SELECT user_email, creation_time, total_bytes_billed, total_bytes_processed FROM `{r['spoke_project_id']}`.`region-{self.settings.GCP_REGION}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE job_type = 'QUERY'"
            for r in rooms
        ]
        jobs_query = " UNION ALL ".join(unions)

        overview_sql = f"""
            WITH researcher_roster AS (
                SELECT primary_email AS researcher_email
                FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}.reg_researchers`
                WHERE is_active = TRUE
            ),
            all_jobs AS ( {jobs_query} ),
            all_researcher_activity AS (
                SELECT user_email AS active_email, creation_time FROM all_jobs
                WHERE user_email IN (SELECT researcher_email FROM researcher_roster)
                UNION ALL
                SELECT principal_email AS active_email, timestamp AS creation_time
                FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_audit_events_curated`
                WHERE principal_email IN (SELECT researcher_email FROM researcher_roster)
            )
            SELECT
                COUNT(DISTINCT IF(creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR), active_email, NULL)) AS active_24h,
                COUNT(DISTINCT IF(creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY), active_email, NULL)) AS active_7d,
                COUNT(DISTINCT IF(creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY), active_email, NULL)) AS active_30d,
                (SELECT COUNTIF(creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)) FROM all_jobs) AS total_queries_24h,
                (SELECT COALESCE(SUM(COALESCE(total_bytes_billed, total_bytes_processed, 0)), 0) FROM all_jobs WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)) AS total_bytes_30d
            FROM all_researcher_activity
        """
        try:
            res = list(self.bq_client.query(overview_sql).result())[0]
            a_24h = int(res["active_24h"] or 0)
            a_7d = int(res["active_7d"] or 0)
            a_30d = int(res["active_30d"] or 0)
            q_24h = int(res["total_queries_24h"] or 0)
            b_30d = int(res["total_bytes_30d"] or 0)
        except Exception as e:
            logger.warning("Falling back to hub_telemetry for fleet overview: %s", e)
            fallback_sql = f"""
                SELECT
                    (SELECT COUNT(DISTINCT user_email) FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics` WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)) AS active_24h,
                    (SELECT COUNT(DISTINCT user_email) FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics` WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)) AS active_7d,
                    (SELECT COUNT(DISTINCT user_email) FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics` WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) AS active_30d,
                    (SELECT COALESCE(SUM(query_count), 0) FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics` WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)) AS total_queries_24h,
                    (SELECT COALESCE(SUM(total_bytes_billed), 0) FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics` WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) AS total_bytes_30d
            """
            fb_res = list(self.bq_client.query(fallback_sql).result())[0]
            a_24h = int(fb_res["active_24h"] or 0)
            a_7d = int(fb_res["active_7d"] or 0)
            a_30d = int(fb_res["active_30d"] or 0)
            q_24h = int(fb_res["total_queries_24h"] or 0)
            b_30d = int(fb_res["total_bytes_30d"] or 0)

        total_storage_bytes = 0
        for room in rooms:
            for b_uri in [room.get("inbound_bucket"), room.get("export_bucket")]:
                if not b_uri:
                    continue
                b_name = b_uri.replace("gs://", "").strip().rstrip("/")
                try:
                    for blob in self.gcs_client.bucket(b_name).list_blobs():
                        if blob.size:
                            total_storage_bytes += blob.size
                except Exception as e:
                    logger.warning("Failed reading storage for bucket %s: %s", b_name, e)

        return FleetTelemetryOverview(
            active_researchers_24h=a_24h,
            active_researchers_7d=a_7d,
            active_researchers_30d=a_30d,
            total_queries_24h=q_24h,
            total_bytes_scanned_30d=b_30d,
            total_fleet_storage_bytes=total_storage_bytes,
        )

    def get_queries(
        self,
        room_id: Optional[str] = None,
        user_email: Optional[str] = None,
        researchers_only: bool = False,
        limit: int = 50,
    ) -> List[QueryJobItem]:
        """Fetch sanitized query jobs across spoke projects or filtered by room and user."""
        rooms = self._get_active_spoke_projects(room_id=room_id)
        if not rooms:
            return []

        selects = [
            f"""SELECT job_id, '{r['room_id']}' AS room_id, project_id, user_email, query AS raw_query,
                COALESCE(total_bytes_billed, total_bytes_processed, 0) AS bytes_billed,
                COALESCE(total_slot_ms, 0) AS slot_ms, start_time, end_time,
                TIMESTAMP_DIFF(end_time, start_time, SECOND) AS duration_seconds, state,
                error_result.message AS error_message, creation_time
                FROM `{r['spoke_project_id']}`.`region-{self.settings.GCP_REGION}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
                WHERE job_type = 'QUERY'"""
            for r in rooms
        ]
        unions = " UNION ALL ".join(selects)

        where_clauses, params = [], []
        if user_email:
            where_clauses.append("user_email = @user_email")
            params.append(bigquery.ScalarQueryParameter("user_email", "STRING", user_email.strip()))
        elif researchers_only:
            where_clauses.append("user_email NOT LIKE '%gserviceaccount.com' AND user_email NOT LIKE '%system@google.com' AND user_email NOT LIKE 'admin@%'")

        where_stmt = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT * FROM ({unions}) {where_stmt} ORDER BY creation_time DESC LIMIT {int(limit)}"

        try:
            results = self.bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
            items = []
            for row in results:
                raw_q = row["raw_query"] or ""
                items.append(
                    QueryJobItem(
                        job_id=row["job_id"], room_id=row["room_id"], project_id=row["project_id"],
                        user_email=row["user_email"], query_snippet=(raw_q[:200] + "...") if len(raw_q) > 200 else raw_q,
                        bytes_billed=row["bytes_billed"] or 0, slot_ms=row["slot_ms"] or 0,
                        start_time=row["start_time"], end_time=row["end_time"],
                        duration_seconds=float(row["duration_seconds"]) if row["duration_seconds"] is not None else None,
                        state=row["state"] or "DONE", error_message=row["error_message"],
                    )
                )
            return items
        except Exception as e:
            logger.warning("INFORMATION_SCHEMA query failed (%s); retrieving recent audit events as fallback", e)
            feed = self.get_audit_feed(room_id=room_id, category="DATA_ACCESS", limit=limit)
            return [
                QueryJobItem(
                    job_id=ev.event_id, room_id=ev.room_id, project_id=self.settings.GCP_PROJECT_ID,
                    user_email=ev.principal_email, query_snippet=ev.description,
                    bytes_billed=0, slot_ms=0, start_time=ev.timestamp, end_time=ev.timestamp,
                    duration_seconds=0.0, state="DONE", error_message=None
                )
                for ev in feed
            ]

    @cached_endpoint(ttl_seconds=15, key_prefix="telemetry_audit")
    def get_audit_feed(
        self,
        room_id: Optional[str] = None,
        category: Optional[str] = None,
        principal_email: Optional[str] = None,
        researchers_only: bool = False,
        limit: Optional[int] = None,
    ) -> List[AuditLogEvent]:
        """Fetch audit log events from curated ops_audit_events_curated mart."""
        query = f"""
            SELECT log_id, timestamp, room_id, project_id, principal_email, category,
                   service_name, action_name, resource_name, status, severity, description
            FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_audit_events_curated`
            WHERE 1=1
        """
        params: List[bigquery.ScalarQueryParameter] = []
        if room_id:
            query += " AND room_id = @room_id"
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id.strip()))
        if category:
            query += " AND category = @category"
            params.append(bigquery.ScalarQueryParameter("category", "STRING", category.strip()))
        if principal_email:
            query += " AND principal_email = @principal_email"
            params.append(bigquery.ScalarQueryParameter("principal_email", "STRING", principal_email.strip()))
        if researchers_only:
            query += f" AND principal_email IN (SELECT primary_email FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}.reg_researchers` WHERE is_active = TRUE)"

        effective_limit = int(limit) if (limit is not None and limit > 0) else 1000
        query += f" ORDER BY timestamp DESC LIMIT {effective_limit}"
        results = self.bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()

        return [
            AuditLogEvent(
                event_id=row["log_id"], room_id=row["room_id"],
                principal_email=row["principal_email"] or "unknown@domain.com",
                service_name=row["service_name"] or "bigquery.googleapis.com",
                method_name=row.get("action_name") or "UnknownAction",
                resource_name=row.get("resource_name") or "UnknownResource",
                timestamp=row["timestamp"] if row["timestamp"] else datetime.now(timezone.utc),
                severity=row["severity"] or "INFO", status=row["status"] or "SUCCESS",
                category=row.get("category"), description=row.get("description"),
            )
            for row in results
        ]

    def get_daily_compute_metrics(
        self,
        room_id: Optional[str] = None,
        user_email: Optional[str] = None,
        limit: int = 50,
    ) -> List[DailyComputeMetricItem]:
        """Fetch persisted daily compute, AI inference, and storage usage metrics."""
        query = f"SELECT * FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics` WHERE 1=1"
        params: List[bigquery.ScalarQueryParameter] = []
        if room_id:
            query += " AND room_id = @room_id"
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id.strip()))
        if user_email:
            query += " AND user_email = @user_email"
            params.append(bigquery.ScalarQueryParameter("user_email", "STRING", user_email.strip()))
        query += f" ORDER BY usage_date DESC LIMIT {int(limit)}"

        results = self.bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
        return [
            DailyComputeMetricItem(
                usage_date=row["usage_date"], room_id=row["room_id"],
                user_email=row["user_email"], institute_id=row["institute_id"],
                query_count=row["query_count"] or 0, total_bytes_billed=row["total_bytes_billed"] or 0,
                total_slot_hours=float(row["total_slot_hours"] or 0.0),
                notebook_runtime_hours=float(row["notebook_runtime_hours"] or 0.0),
                ai_inference_count=row.get("ai_inference_count") or 0,
                ai_token_count=row.get("ai_token_count") or 0,
                storage_bytes=row["storage_bytes"] or 0,
            )
            for row in results
        ]

    def get_monthly_usage_rollup(
        self,
        room_id: Optional[str] = None,
        institute_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MonthlyUsageRollupItem]:
        """Fetch monthly usage rollup aggregated metrics."""
        query = f"SELECT * FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_monthly_usage_rollup` WHERE 1=1"
        params: List[bigquery.ScalarQueryParameter] = []
        if room_id:
            query += " AND room_id = @room_id"
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id.strip()))
        if institute_id:
            query += " AND institute_id = @institute_id"
            params.append(bigquery.ScalarQueryParameter("institute_id", "STRING", institute_id.strip()))
        query += f" ORDER BY usage_month DESC LIMIT {int(limit)}"

        results = self.bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
        return [
            MonthlyUsageRollupItem(
                usage_month=row["usage_month"], room_id=row["room_id"],
                institute_id=row["institute_id"],
                avg_active_researchers=float(row["avg_active_researchers"] or 0.0),
                total_notebook_hours=float(row["total_notebook_hours"] or 0.0),
                total_query_volume_tb=float(row["total_query_volume_tb"] or 0.0),
                total_slot_hours=float(row["total_slot_hours"] or 0.0),
            )
            for row in results
        ]

    def get_notebook_sessions(
        self,
        room_id: Optional[str] = None,
        user_email: Optional[str] = None,
        limit: int = 50,
    ) -> List[NotebookSessionItem]:
        """Fetch persisted Colab Enterprise and BigQuery Studio notebook sessions."""
        query = f"SELECT * FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_notebook_sessions` WHERE 1=1"
        params: List[bigquery.ScalarQueryParameter] = []
        if room_id:
            query += " AND room_id = @room_id"
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id.strip()))
        if user_email:
            query += " AND user_email = @user_email"
            params.append(bigquery.ScalarQueryParameter("user_email", "STRING", user_email.strip()))
        query += f" ORDER BY session_date DESC LIMIT {int(limit)}"

        results = self.bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
        return [
            NotebookSessionItem(
                room_id=row["room_id"],
                user_email=row["user_email"],
                session_date=row["session_date"],
                notebook_name=row.get("notebook_name"),
                runtime_id=row.get("runtime_id"),
                machine_type=row.get("machine_type"),
                runtime_template_id=row.get("runtime_template_id"),
                total_events=row.get("total_events") or 0,
                session_starts=row.get("session_starts") or 0,
                session_stops=row.get("session_stops") or 0,
                total_sessions=row.get("total_sessions") or 1,
                total_active_hours=float(row.get("total_active_hours") or 0.0),
                first_session_start=row.get("first_session_start"),
                last_session_end=row.get("last_session_end"),
            )
            for row in results
        ]

    def sync_telemetry_pipelines(self) -> TelemetrySyncResponse:
        """Execute all BigQuery curation and aggregation stored procedures."""
        procs = [
            "sp_sync_curated_audit_events", "sp_sync_notebook_session_metrics",
            "sp_sync_ai_usage_metrics", "sp_aggregate_daily_compute_metrics", "sp_rollup_monthly_usage",
        ]
        for p in procs:
            self.bq_client.query(f"CALL `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.{p}`()").result()
        return TelemetrySyncResponse(
            status="SUCCESS", sync_timestamp=datetime.now(timezone.utc),
            message="All 5 telemetry curation and aggregation stored procedures executed successfully.",
        )

    def get_room_inventory(self, room_id: str) -> RoomAssetInventory:
        """Query BigQuery datasets/tables and Cloud Storage buckets for room asset inventory."""
        target_room = room_id.strip() if isinstance(room_id, str) else ""
        rooms = self._get_active_spoke_projects(room_id=target_room)
        if not rooms:
            raise ValueError(f"Active research room '{room_id}' not found in registry.")

        room = rooms[0]
        spoke_project = room["spoke_project_id"]
        local_tables, shared_tables = 0, 0
        try:
            for ds in self.bq_client.list_datasets(spoke_project):
                tables = list(self.bq_client.list_tables(f"{spoke_project}.{ds.dataset_id}"))
                if ds.dataset_id.startswith("spoke_local"):
                    local_tables += len(tables)
                else:
                    shared_tables += len(tables)
        except Exception as e:
            logger.warning("Error listing BigQuery tables for %s: %s", spoke_project, e)

        inbound_bytes, inbound_objs, notebooks_count = 0, 0, 0
        export_bytes, export_objs = 0, 0

        if room.get("inbound_bucket"):
            b_name = room["inbound_bucket"].replace("gs://", "").strip().rstrip("/")
            try:
                for blob in self.gcs_client.bucket(b_name).list_blobs():
                    inbound_objs += 1
                    if blob.size:
                        inbound_bytes += blob.size
                    if blob.name.endswith(".ipynb"):
                        notebooks_count += 1
            except Exception as e:
                logger.warning("Error listing inbound bucket %s: %s", b_name, e)

        if room.get("export_bucket"):
            b_name = room["export_bucket"].replace("gs://", "").strip().rstrip("/")
            try:
                for blob in self.gcs_client.bucket(b_name).list_blobs():
                    export_objs += 1
                    if blob.size:
                        export_bytes += blob.size
            except Exception as e:
                logger.warning("Error listing export bucket %s: %s", b_name, e)

        return RoomAssetInventory(
            room_id=target_room, local_tables_count=local_tables,
            shared_tables_count=shared_tables, total_accessible_tables=local_tables + shared_tables,
            inbound_bytes=inbound_bytes, inbound_objects=inbound_objs,
            export_bytes=export_bytes, export_objects=export_objs, notebooks_count=notebooks_count,
        )

    def get_room_activity(self, room_id: str, limit: int = 50, researchers_only: bool = True) -> RoomActivitySummary:
        """Compute last active session timestamp, researcher queries, and live notebook execution metrics."""
        target_room = room_id.strip() if isinstance(room_id, str) else ""
        recent_queries = self.get_queries(room_id=target_room, researchers_only=researchers_only, limit=limit)
        recent_audits = self.get_audit_feed(room_id=target_room, researchers_only=researchers_only, limit=limit)
        if not recent_audits and researchers_only:
            recent_audits = self.get_audit_feed(room_id=target_room, limit=limit)

        last_active_ts = recent_audits[0].timestamp if recent_audits else (recent_queries[0].start_time if recent_queries else None)
        active_email = recent_audits[0].principal_email if recent_audits else (recent_queries[0].user_email if recent_queries else None)

        total_queries = 0
        researcher_queries = 0
        try:
            q_sum = f"""
                SELECT 
                    COALESCE(SUM(query_count), 0) AS total_q,
                    COALESCE(SUM(IF(user_email NOT LIKE '%gserviceaccount.com' AND user_email NOT LIKE '%system@google.com' AND user_email NOT LIKE 'admin@%', query_count, 0)), 0) AS researcher_q
                FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_daily_compute_metrics`
                WHERE room_id = @room_id
            """
            params = [bigquery.ScalarQueryParameter("room_id", "STRING", target_room)]
            res = list(self.bq_client.query(q_sum, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())
            if res:
                total_queries = int(res[0]["total_q"] or 0)
                researcher_queries = int(res[0]["researcher_q"] or 0)
        except Exception as e:
            logger.warning("Could not calculate total queries for %s: %s", target_room, e)
            total_queries = len(recent_queries)
            researcher_queries = len(recent_queries)

        total_nb_runs = 0
        total_nb_hours = 0.0
        try:
            nb_sql = f"""
                SELECT 
                    COALESCE(SUM(total_sessions), 0) AS total_sessions,
                    COALESCE(SUM(total_active_hours), 0.0) AS total_hours
                FROM `{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_notebook_sessions`
                WHERE room_id = @room_id
                  AND user_email NOT LIKE '%gserviceaccount.com'
                  AND user_email NOT LIKE '%system@google.com'
                  AND user_email NOT LIKE 'admin@%'
            """
            nb_res = list(self.bq_client.query(nb_sql, job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("room_id", "STRING", target_room)
            ])).result())
            if nb_res:
                total_nb_runs = int(nb_res[0]["total_sessions"] or 0)
                total_nb_hours = float(nb_res[0]["total_hours"] or 0.0)
        except Exception as e:
            logger.warning("Could not calculate notebook sessions for %s: %s", target_room, e)

        active_name = None
        if active_email:
            prefix = active_email.split("@")[0].replace("_", ".").split(".")
            active_name = " ".join([p.capitalize() for p in prefix])

        return RoomActivitySummary(
            room_id=target_room,
            recent_queries=recent_queries,
            recent_audit_events=recent_audits,
            last_active_session=last_active_ts,
            total_queries_count=total_queries,
            researcher_queries_count=researcher_queries,
            total_notebook_runs=total_nb_runs,
            total_notebook_hours=total_nb_hours,
            active_researcher_email=active_email,
            active_researcher_name=active_name,
        )


_telemetry_service_instance: Optional[TelemetryService] = None


def get_telemetry_service() -> TelemetryService:
    """Dependency provider for TelemetryService."""
    global _telemetry_service_instance
    if _telemetry_service_instance is None:
        _telemetry_service_instance = TelemetryService()
    return _telemetry_service_instance

