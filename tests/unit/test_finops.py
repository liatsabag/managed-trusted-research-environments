"""Unit and integration tests for FinOps hierarchical SKU and telemetry attribution engine."""

import unittest
from fastapi import HTTPException

from backend.app.api.v1.finops import (
    get_allocation_matrix,
    get_finops_summary,
    get_forecast,
    get_institute_cost,
    get_researcher_attributions,
    get_room_cost,
)
from backend.app.models.finops import (
    FinOpsAllocationMatrixResponse,
    FinOpsForecastResponse,
    FinOpsSummaryResponse,
    InstituteCostBreakdown,
    ResearcherCostDetail,
    ResearcherSKUAttribution,
    ResearcherTelemetryUsage,
    RoomFinOpsDetailResponse,
    SKUBillingItem,
    SharedOverheadDetail,
)
from backend.app.services.finops import FinOpsService, get_finops_service


class TestFinOpsModels(unittest.TestCase):
    """Test suite for FinOps Pydantic models."""

    def test_sku_billing_item_model(self):
        """Verify SKUBillingItem model serialization."""
        item = SKUBillingItem(
            sku_id="D30B-7D37-47C2",
            sku_description="Analysis",
            service_description="BigQuery",
            usage_amount=0.004,
            usage_unit="tib",
            cost=0.02,
            currency="USD",
        )
        self.assertEqual(item.service_description, "BigQuery")
        self.assertEqual(item.cost, 0.02)
        self.assertEqual(item.usage_amount, 0.004)

    def test_researcher_telemetry_usage_model(self):
        """Verify ResearcherTelemetryUsage model."""
        usage = ResearcherTelemetryUsage(
            total_bytes_billed=73400320,
            query_count=24,
            notebook_runtime_hours=0.5,
            ai_token_count=13500,
            storage_bytes=8090,
        )
        self.assertEqual(usage.total_bytes_billed, 73400320)
        self.assertEqual(usage.ai_token_count, 13500)

    def test_researcher_cost_detail_model(self):
        """Verify ResearcherCostDetail model hierarchy."""
        sku_attr = ResearcherSKUAttribution(
            sku_id="D30B-7D37-47C2",
            sku_description="Analysis",
            weight=0.25,
            formula_applied="W = bytes_billed / total_bytes",
            allocated_cost=25.0,
        )
        res = ResearcherCostDetail(
            researcher_id="res-onc-001",
            name="Dr. Oren Katz",
            email="dr.oren.katz@liatsabag.altostrat.com",
            institute_id="inst-mskcc",
            telemetry_usage=ResearcherTelemetryUsage(total_bytes_billed=1048576),
            sku_attributions=[sku_attr],
            total_allocated_cost=25.0,
        )
        self.assertEqual(res.researcher_id, "res-onc-001")
        self.assertEqual(res.total_allocated_cost, 25.0)
        self.assertEqual(len(res.sku_attributions), 1)

    def test_room_finops_detail_model(self):
        """Verify RoomFinOpsDetailResponse model and reconciliation invariant."""
        room = RoomFinOpsDetailResponse(
            room_id="rr-oncology-01",
            room_name="Oncology Research Room",
            spoke_project_id="gcp-rr-spoke-oncology-01",
            institute_id="inst-mskcc",
            total_invoiced_cost=100.0,
            currency="USD",
            skus=[],
            researchers=[],
            shared_overhead=SharedOverheadDetail(
                admin_usage=ResearcherTelemetryUsage(total_bytes_billed=5000),
                sku_attributions=[],
                total_shared_overhead_cost=100.0,
            ),
            reconciliation_variance=0.0,
            reconciliation_status="BALANCED",
        )
        self.assertEqual(room.room_id, "rr-oncology-01")
        self.assertEqual(room.reconciliation_status, "BALANCED")
        self.assertEqual(room.reconciliation_variance, 0.0)


class TestFinOpsWeightFormulas(unittest.TestCase):
    """Test suite for mathematical weight formulas across SKU categories."""

    def setUp(self):
        self.service = FinOpsService.__new__(FinOpsService)
        self.service.hub_project = "gcp-rr-hub-core"
        self.service.telemetry_dataset = "hub_telemetry"
        self.service.registry_dataset = "hub_registry"

    def test_bigquery_bytes_attribution(self):
        """Verify BigQuery SKU costs apportioned proportionally by bytes billed."""
        researchers = [
            {"primary_email": "r1@test.com", "researcher_id": "res-1"},
            {"primary_email": "r2@test.com", "researcher_id": "res-2"},
        ]
        metrics = {
            "r1@test.com": {"total_bytes_billed": 3000, "query_count": 10},
            "r2@test.com": {"total_bytes_billed": 1000, "query_count": 5},
            "admin@test.com": {"total_bytes_billed": 6000, "query_count": 20},
        }
        sku = SKUBillingItem(
            service_description="BigQuery",
            sku_description="Analysis",
            cost=100.0,
        )
        res_attrs, ovh_attr = self.service._compute_attribution_for_sku(researchers, metrics, sku)

        self.assertAlmostEqual(res_attrs["r1@test.com"].weight, 0.30)
        self.assertAlmostEqual(res_attrs["r2@test.com"].weight, 0.10)
        self.assertAlmostEqual(res_attrs["r1@test.com"].allocated_cost, 30.0)
        self.assertAlmostEqual(res_attrs["r2@test.com"].allocated_cost, 10.0)
        self.assertAlmostEqual(ovh_attr.allocated_cost, 60.0)
        total_alloc = sum(a.allocated_cost for a in res_attrs.values()) + ovh_attr.allocated_cost
        self.assertAlmostEqual(total_alloc, sku.cost)

    def test_storage_proportional_weighting(self):
        """Verify Cloud Storage SKU costs apportioned proportionally by storage_bytes."""
        researchers = [
            {"primary_email": "r1@test.com", "researcher_id": "res-1"},
            {"primary_email": "r2@test.com", "researcher_id": "res-2"},
        ]
        metrics = {
            "r1@test.com": {"storage_bytes": 8000},
            "r2@test.com": {"storage_bytes": 2000},
            "admin@test.com": {"storage_bytes": 90000},
        }
        sku = SKUBillingItem(
            service_description="Cloud Storage",
            sku_description="Standard Storage Israel",
            cost=50.0,
        )
        res_attrs, ovh_attr = self.service._compute_attribution_for_sku(researchers, metrics, sku)

        self.assertAlmostEqual(res_attrs["r1@test.com"].weight, 0.08)
        self.assertAlmostEqual(res_attrs["r2@test.com"].weight, 0.02)
        self.assertAlmostEqual(res_attrs["r1@test.com"].allocated_cost, 4.0)
        self.assertAlmostEqual(res_attrs["r2@test.com"].allocated_cost, 1.0)
        self.assertAlmostEqual(ovh_attr.allocated_cost, 45.0)
        total_alloc = sum(a.allocated_cost for a in res_attrs.values()) + ovh_attr.allocated_cost
        self.assertAlmostEqual(total_alloc, sku.cost)

    def test_compute_notebook_hours_weighting(self):
        """Verify Compute Engine SKU weights based on notebook_runtime_hours."""
        researchers = [
            {"primary_email": "r1@test.com", "researcher_id": "res-1"},
            {"primary_email": "r2@test.com", "researcher_id": "res-2"},
        ]
        metrics = {
            "r1@test.com": {"notebook_runtime_hours": 6.0},
            "r2@test.com": {"notebook_runtime_hours": 2.0},
            "service-nb@iam.gserviceaccount.com": {"notebook_runtime_hours": 2.0},
        }
        sku = SKUBillingItem(
            service_description="Compute Engine",
            sku_description="N1 Predefined Instance Core running in Israel",
            cost=200.0,
        )
        res_attrs, ovh_attr = self.service._compute_attribution_for_sku(researchers, metrics, sku)

        self.assertAlmostEqual(res_attrs["r1@test.com"].weight, 0.60)
        self.assertAlmostEqual(res_attrs["r2@test.com"].weight, 0.20)
        self.assertAlmostEqual(res_attrs["r1@test.com"].allocated_cost, 120.0)
        self.assertAlmostEqual(res_attrs["r2@test.com"].allocated_cost, 40.0)
        self.assertAlmostEqual(ovh_attr.allocated_cost, 40.0)
        total_alloc = sum(a.allocated_cost for a in res_attrs.values()) + ovh_attr.allocated_cost
        self.assertAlmostEqual(total_alloc, sku.cost)

    def test_ai_tokens_weighting(self):
        """Verify Vertex AI SKU weights based on ai_token_count."""
        researchers = [
            {"primary_email": "r1@test.com", "researcher_id": "res-1"},
            {"primary_email": "r2@test.com", "researcher_id": "res-2"},
        ]
        metrics = {
            "r1@test.com": {"ai_token_count": 8000, "ai_inference_count": 10},
            "r2@test.com": {"ai_token_count": 2000, "ai_inference_count": 2},
        }
        sku = SKUBillingItem(
            service_description="Vertex AI",
            sku_description="Gemini 1.5 Pro Output Tokens",
            cost=10.0,
        )
        res_attrs, ovh_attr = self.service._compute_attribution_for_sku(researchers, metrics, sku)

        self.assertAlmostEqual(res_attrs["r1@test.com"].weight, 0.80)
        self.assertAlmostEqual(res_attrs["r2@test.com"].weight, 0.20)
        self.assertAlmostEqual(res_attrs["r1@test.com"].allocated_cost, 8.0)
        self.assertAlmostEqual(res_attrs["r2@test.com"].allocated_cost, 2.0)
        self.assertAlmostEqual(ovh_attr.allocated_cost, 0.0)
        total_alloc = sum(a.allocated_cost for a in res_attrs.values()) + ovh_attr.allocated_cost
        self.assertAlmostEqual(total_alloc, sku.cost)

    def test_zero_usage_sku_attribution(self):
        """Verify SKUs with 0 usage are attributed 100% to shared overhead."""
        researchers = [{"primary_email": "r1@test.com", "researcher_id": "res-1"}]
        metrics = {}
        sku = SKUBillingItem(
            service_description="Cloud Storage",
            sku_description="Standard Storage Israel",
            cost=15.0,
        )
        res_attrs, ovh_attr = self.service._compute_attribution_for_sku(researchers, metrics, sku)
        self.assertEqual(res_attrs["r1@test.com"].allocated_cost, 0.0)
        self.assertEqual(ovh_attr.allocated_cost, 15.0)
        self.assertEqual(ovh_attr.weight, 1.0)


class TestFinOpsServiceLive(unittest.TestCase):
    """Test suite for FinOpsService live GCP BigQuery execution."""

    def setUp(self):
        self.service = FinOpsService()

    def test_live_summary_reconciliation(self):
        """Verify live FinOps summary reconciliation across the fleet."""
        summary = self.service.get_summary()
        self.assertIsInstance(summary, FinOpsSummaryResponse)
        self.assertGreaterEqual(summary.total_fleet_cost, 0.0)
        reconciled = summary.total_researcher_cost + summary.total_shared_overhead_cost + summary.hub_infrastructure_cost
        self.assertAlmostEqual(summary.total_fleet_cost, reconciled, places=2)

    def test_live_room_detail_reconciliation(self):
        """Verify zero-drift reconciliation for every room."""
        for room_id in ["rr-oncology-01", "rr-genomics-02", "rr-cardio-03", "rr-neurology-04"]:
            room = self.service.get_room_cost(room_id)
            self.assertIsInstance(room, RoomFinOpsDetailResponse)
            self.assertEqual(room.room_id, room_id)
            self.assertEqual(room.reconciliation_status, "BALANCED")
            self.assertAlmostEqual(room.reconciliation_variance, 0.0, places=2)
            self.assertGreater(len(room.researchers), 0)

    def test_live_allocation_matrix(self):
        """Verify live allocation matrix endpoint."""
        matrix = self.service.get_allocation_matrix()
        self.assertIsInstance(matrix, FinOpsAllocationMatrixResponse)
        self.assertEqual(matrix.reconciliation_status, "BALANCED")
        self.assertAlmostEqual(matrix.variance, 0.0, places=2)

    def test_live_forecast(self):
        """Verify live forecast calculation."""
        fc = self.service.get_forecast()
        self.assertIsInstance(fc, FinOpsForecastResponse)
        self.assertGreater(fc.days_elapsed, 0)
        self.assertGreaterEqual(fc.forecasted_monthly_cost, 0.0)


class TestFinOpsAPIControllers(unittest.TestCase):
    """Test suite for FastAPI route controllers."""

    def setUp(self):
        self.service = get_finops_service()

    def test_api_summary(self):
        """Test GET /finops/summary controller."""
        res = get_finops_summary(service=self.service)
        self.assertIsInstance(res, FinOpsSummaryResponse)

    def test_api_researchers(self):
        """Test GET /finops/researchers controller."""
        res = get_researcher_attributions(service=self.service)
        self.assertIsInstance(res, list)

    def test_api_room_cost(self):
        """Test GET /finops/rooms/{room_id} controller."""
        res = get_room_cost(room_id="rr-oncology-01", service=self.service)
        self.assertIsInstance(res, RoomFinOpsDetailResponse)
        self.assertEqual(res.room_id, "rr-oncology-01")

    def test_api_room_cost_404(self):
        """Test 404 for nonexistent room."""
        with self.assertRaises(HTTPException) as ctx:
            get_room_cost(room_id="rr-nonexistent-99", service=self.service)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_api_institute_cost(self):
        """Test GET /finops/institutes/{institute_id} controller."""
        res = get_institute_cost(institute_id="inst-mskcc", service=self.service)
        self.assertIsInstance(res, InstituteCostBreakdown)

    def test_api_matrix(self):
        """Test GET /finops/matrix controller."""
        res = get_allocation_matrix(service=self.service)
        self.assertIsInstance(res, FinOpsAllocationMatrixResponse)

    def test_api_forecast(self):
        """Test GET /finops/forecast controller."""
        res = get_forecast(service=self.service)
        self.assertIsInstance(res, FinOpsForecastResponse)


if __name__ == "__main__":
    unittest.main()
