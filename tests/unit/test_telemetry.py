"""Unit and integration tests for Telemetry service, models, and API endpoints."""

import unittest
from datetime import date, datetime, timezone

from fastapi import HTTPException

from backend.app.api.v1.telemetry import (
    get_audit_feed,
    get_daily_compute_metrics,
    get_fleet_overview,
    get_monthly_usage_rollup,
    get_queries,
    get_room_activity,
    get_room_inventory,
    trigger_telemetry_sync,
)
from backend.app.models.telemetry import (
    AuditLogEvent,
    DailyComputeMetricItem,
    FleetTelemetryOverview,
    MonthlyUsageRollupItem,
    QueryJobItem,
    RoomActivitySummary,
    RoomAssetInventory,
    TelemetrySyncResponse,
)
from backend.app.services.telemetry import TelemetryService, get_telemetry_service


class TestTelemetryModels(unittest.TestCase):
    """Test suite for Telemetry Pydantic models."""

    def test_query_job_item_model(self):
        """Verify QueryJobItem instantiation and defaults."""
        item = QueryJobItem(
            job_id="job-1234",
            room_id="rr-oncology-01",
            project_id="gcp-rr-spoke-oncology-01",
            user_email="dr.oren.katz@mskcc.altostrat.com",
            query_snippet="SELECT * FROM cohort",
            bytes_billed=1048576,
            slot_ms=250,
            duration_seconds=1.5,
            state="DONE",
        )
        self.assertEqual(item.job_id, "job-1234")
        self.assertEqual(item.room_id, "rr-oncology-01")
        self.assertEqual(item.bytes_billed, 1048576)
        self.assertEqual(item.duration_seconds, 1.5)

    def test_audit_log_event_model(self):
        """Verify AuditLogEvent instantiation."""
        event = AuditLogEvent(
            event_id="evt-999",
            room_id="rr-oncology-01",
            principal_email="dr.oren.katz@mskcc.altostrat.com",
            service_name="bigquery.googleapis.com",
            method_name="google.cloud.bigquery.v2.JobService.InsertJob",
            resource_name="projects/gcp-rr-spoke-oncology-01/jobs/123",
            timestamp=datetime.now(timezone.utc),
            severity="INFO",
            status="SUCCESS",
        )
        self.assertEqual(event.event_id, "evt-999")
        self.assertEqual(event.status, "SUCCESS")

    def test_daily_compute_metric_model(self):
        """Verify DailyComputeMetricItem instantiation."""
        item = DailyComputeMetricItem(
            usage_date=date(2026, 9, 28),
            room_id="rr-oncology-01",
            user_email="admin@liatsabag.altostrat.com",
            institute_id="inst-mskcc",
            query_count=20,
            total_bytes_billed=1048576,
            total_slot_hours=0.005,
            notebook_runtime_hours=1.5,
            storage_bytes=50000,
        )
        self.assertEqual(item.room_id, "rr-oncology-01")
        self.assertEqual(item.query_count, 20)

    def test_monthly_usage_rollup_model(self):
        """Verify MonthlyUsageRollupItem instantiation."""
        item = MonthlyUsageRollupItem(
            usage_month=date(2026, 9, 1),
            room_id="rr-oncology-01",
            institute_id="inst-mskcc",
            avg_active_researchers=1.5,
            total_notebook_hours=10.0,
            total_query_volume_tb=0.5,
            total_slot_hours=0.05,
        )
        self.assertEqual(item.room_id, "rr-oncology-01")
        self.assertEqual(item.avg_active_researchers, 1.5)

    def test_room_asset_inventory_model(self):
        """Verify RoomAssetInventory calculations."""
        inv = RoomAssetInventory(
            room_id="rr-oncology-01",
            local_tables_count=4,
            shared_tables_count=4,
            total_accessible_tables=8,
            inbound_bytes=127010,
            inbound_objects=8,
            export_bytes=3567,
            export_objects=10,
            notebooks_count=4,
        )
        self.assertEqual(inv.total_accessible_tables, 8)
        self.assertEqual(inv.notebooks_count, 4)

    def test_fleet_overview_model(self):
        """Verify FleetTelemetryOverview metrics."""
        overview = FleetTelemetryOverview(
            active_researchers_24h=8,
            active_researchers_7d=8,
            active_researchers_30d=8,
            total_queries_24h=120,
            total_bytes_scanned_30d=1073741824,
            total_fleet_storage_bytes=376466,
        )
        self.assertEqual(overview.active_researchers_24h, 8)
        self.assertEqual(overview.total_queries_24h, 120)


class TestTelemetryService(unittest.TestCase):
    """Test suite for TelemetryService with live GCP resources."""

    def setUp(self):
        self.service = TelemetryService()

    def test_get_active_spoke_projects(self):
        """Verify dynamic discovery of active research rooms."""
        rooms = self.service._get_active_spoke_projects()
        self.assertGreaterEqual(len(rooms), 4)
        room_ids = [r["room_id"] for r in rooms]
        self.assertIn("rr-oncology-01", room_ids)
        self.assertIn("rr-genomics-02", room_ids)
        self.assertIn("rr-cardio-03", room_ids)
        self.assertIn("rr-neurology-04", room_ids)

    def test_get_fleet_overview_live(self):
        """Verify live fleet overview computation."""
        overview = self.service.get_fleet_overview()
        self.assertIsInstance(overview, FleetTelemetryOverview)
        self.assertGreaterEqual(overview.total_fleet_storage_bytes, 0)
        self.assertGreaterEqual(overview.active_researchers_30d, 0)

    def test_get_queries_live(self):
        """Verify live query jobs fetching across rooms."""
        queries = self.service.get_queries(limit=5)
        self.assertIsInstance(queries, list)
        for q in queries:
            self.assertIsInstance(q, QueryJobItem)
            self.assertIsNotNone(q.job_id)
            self.assertIsNotNone(q.project_id)

    def test_get_queries_filtered_by_room(self):
        """Verify query jobs filtered by a single room."""
        queries = self.service.get_queries(room_id="rr-oncology-01", limit=5)
        self.assertIsInstance(queries, list)
        for q in queries:
            self.assertEqual(q.room_id, "rr-oncology-01")

    def test_get_audit_feed_live(self):
        """Verify live audit feed retrieval from curated table."""
        audits = self.service.get_audit_feed(limit=5)
        self.assertIsInstance(audits, list)

    def test_get_daily_compute_metrics_live(self):
        """Verify live daily compute metrics query."""
        metrics = self.service.get_daily_compute_metrics(limit=5)
        self.assertIsInstance(metrics, list)
        for m in metrics:
            self.assertIsInstance(m, DailyComputeMetricItem)
            self.assertIsNotNone(m.usage_date)

    def test_get_monthly_usage_rollup_live(self):
        """Verify live monthly usage rollup query."""
        rollups = self.service.get_monthly_usage_rollup(limit=5)
        self.assertIsInstance(rollups, list)
        for r in rollups:
            self.assertIsInstance(r, MonthlyUsageRollupItem)
            self.assertIsNotNone(r.usage_month)

    def test_get_room_inventory_live(self):
        """Verify room asset inventory aggregation."""
        inventory = self.service.get_room_inventory("rr-oncology-01")
        self.assertIsInstance(inventory, RoomAssetInventory)
        self.assertEqual(inventory.room_id, "rr-oncology-01")
        self.assertGreater(inventory.local_tables_count, 0)
        self.assertGreaterEqual(inventory.shared_tables_count, 0)
        self.assertEqual(inventory.total_accessible_tables, inventory.local_tables_count + inventory.shared_tables_count)
        self.assertGreater(inventory.inbound_objects, 0)
        self.assertGreater(inventory.notebooks_count, 0)

    def test_get_room_inventory_not_found(self):
        """Verify non-existent room inventory raises ValueError."""
        with self.assertRaises(ValueError):
            self.service.get_room_inventory("rr-invalid-99")

    def test_get_room_activity_live(self):
        """Verify room activity summary retrieval."""
        activity = self.service.get_room_activity("rr-oncology-01")
        self.assertIsInstance(activity, RoomActivitySummary)
        self.assertEqual(activity.room_id, "rr-oncology-01")
        self.assertIsInstance(activity.recent_queries, list)
        self.assertIsInstance(activity.recent_audit_events, list)


class TestTelemetryAPIEndpoints(unittest.TestCase):
    """Test suite for Telemetry API controller functions."""

    def setUp(self):
        self.service = get_telemetry_service()

    def test_api_overview(self):
        """Verify GET /telemetry/overview controller."""
        res = get_fleet_overview(service=self.service)
        self.assertIsInstance(res, FleetTelemetryOverview)

    def test_api_queries(self):
        """Verify GET /telemetry/queries controller."""
        res = get_queries(limit=10, service=self.service)
        self.assertIsInstance(res, list)

    def test_api_audit_feed(self):
        """Verify GET /telemetry/audit-feed controller."""
        res = get_audit_feed(limit=10, service=self.service)
        self.assertIsInstance(res, list)

    def test_api_daily_metrics(self):
        """Verify GET /telemetry/metrics/daily controller."""
        res = get_daily_compute_metrics(limit=10, service=self.service)
        self.assertIsInstance(res, list)

    def test_api_monthly_metrics(self):
        """Verify GET /telemetry/metrics/monthly controller."""
        res = get_monthly_usage_rollup(limit=10, service=self.service)
        self.assertIsInstance(res, list)

    def test_api_room_inventory(self):
        """Verify GET /telemetry/rooms/{room_id}/inventory controller."""
        res = get_room_inventory("rr-oncology-01", service=self.service)
        self.assertIsInstance(res, RoomAssetInventory)
        self.assertEqual(res.room_id, "rr-oncology-01")

    def test_api_room_inventory_404(self):
        """Verify 404 response on unknown room inventory."""
        with self.assertRaises(HTTPException) as ctx:
            get_room_inventory("rr-nonexistent-99", service=self.service)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_api_room_activity(self):
        """Verify GET /telemetry/rooms/{room_id}/activity controller."""
        res = get_room_activity("rr-oncology-01", service=self.service)
        self.assertIsInstance(res, RoomActivitySummary)
        self.assertEqual(res.room_id, "rr-oncology-01")


if __name__ == "__main__":
    unittest.main()
