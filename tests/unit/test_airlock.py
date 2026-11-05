"""Unit tests for Airlock Egress Governance and Gemini Risk Scanner."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# Defensive shim for environments where anyio subdependency is not installed
class AnyioMock(ModuleType):
    def __getattr__(self, name):
        return MagicMock

for mod_name in ["anyio", "anyio.abc", "anyio.to_thread", "anyio.lowlevel"]:
    if mod_name not in sys.modules:
        m = AnyioMock(mod_name)
        m.ObjectReceiveStream = MagicMock
        m.ObjectSendStream = MagicMock
        m.CapacityLimiter = MagicMock
        m.to_thread = MagicMock()
        sys.modules[mod_name] = m

import unittest
from backend.app.models.airlock import (
    AirlockActionRequest,
    AirlockActionResponse,
    AirlockExportCandidate,
    AirlockScanRequest,
)
from backend.app.services.gemini_risk_service import GeminiRiskService


class TestAirlockGovernance(unittest.TestCase):
    """Test suite for Airlock models and GeminiRiskService."""

    def setUp(self):
        """Mock out GCP clients on GeminiRiskService instance."""
        with patch("google.cloud.bigquery.Client"), \
             patch("google.cloud.storage.Client"), \
             patch("google.cloud.dlp_v2.DlpServiceClient"):
            self.service = GeminiRiskService()
            self.service.bq_client = MagicMock()
            self.service.storage_client = MagicMock()
            self.service.dlp_client = MagicMock()

    def test_export_candidate_model_defaults(self):
        """Verify candidate model initializes with PENDING_SCAN state and default fields."""
        candidate = AirlockExportCandidate(
            room_id="rr-oncology-01",
            file_name="cohort_summary.csv",
            bucket_name="rr-oncology-01-export",
            file_size_bytes=4096,
        )
        self.assertEqual(candidate.status, "PENDING_SCAN")
        self.assertEqual(candidate.risk_score, None)
        self.assertEqual(candidate.pii_tokens_detected, [])
        self.assertEqual(candidate.k_anonymity_violation, False)

    def test_action_request_and_response_serialization(self):
        """Verify approval and rejection action modeling."""
        req = AirlockActionRequest(
            room_id="rr-oncology-01",
            file_name="aggregate_survival.csv",
            action="APPROVE",
            comment="De-identified summary with k >= 10",
        )
        self.assertEqual(req.action, "APPROVE")
        self.assertEqual(req.room_id, "rr-oncology-01")

        res = AirlockActionResponse(
            room_id=req.room_id,
            file_name=req.file_name,
            action=req.action,
            status="APPROVED",
            message="Export candidate approved.",
        )
        self.assertEqual(res.status, "APPROVED")
        self.assertIn("Export candidate", res.message)

    def test_take_decision_uses_parameterized_merge(self):
        """Verify take_decision executes parameterized BigQuery MERGE."""
        req = AirlockActionRequest(
            room_id="rr-oncology-01",
            file_name="pfs_curves.png",
            action="APPROVE",
            comment="Safe visual figure",
        )
        self.service.bq_client.query.return_value.result.return_value = None

        response = self.service.take_decision(req)
        self.assertEqual(response.status, "APPROVED")
        self.assertEqual(response.action, "APPROVE")

        # Verify BigQuery client was invoked with a MERGE query and QueryJobConfig
        self.service.bq_client.query.assert_called_once()
        args, kwargs = self.service.bq_client.query.call_args
        sql_query = args[0]
        self.assertIn("MERGE", sql_query)
        self.assertIn("@room_id", sql_query)
        self.assertIn("@file_name", sql_query)
        self.assertIn("@decision_status", sql_query)

        job_config = kwargs.get("job_config")
        self.assertIsNotNone(job_config)
        param_names = [p.name for p in job_config.query_parameters]
        self.assertIn("room_id", param_names)
        self.assertIn("file_name", param_names)
        self.assertIn("decision_status", param_names)

    def test_get_export_buckets_parameterization(self):
        """Verify _get_export_buckets binds room_id parameter when provided."""
        self.service.bq_client.query.return_value.result.return_value = [
            {"room_id": "rr-oncology-01", "export_bucket": "gs://rr-oncology-01-export", "spoke_project_id": "spoke-01"}
        ]

        buckets = self.service._get_export_buckets(room_id="rr-oncology-01")
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["bucket_name"], "rr-oncology-01-export")

        args, kwargs = self.service.bq_client.query.call_args
        sql_query = args[0]
        self.assertIn("@room_id", sql_query)
        job_config = kwargs.get("job_config")
        self.assertIsNotNone(job_config)
        param_names = [p.name for p in job_config.query_parameters]
        self.assertIn("room_id", param_names)

    def test_inspect_content_with_dlp_parses_findings(self):
        """Verify Stage 1 Cloud DLP inspects content and surfaces detected infotypes."""
        mock_finding = MagicMock()
        mock_finding.info_type.name = "EMAIL_ADDRESS"
        mock_finding.quote = "doctor@hospital.org"

        mock_response = MagicMock()
        mock_response.result.findings = [mock_finding]
        self.service.dlp_client.inspect_content.return_value = mock_response

        dlp_res = self.service._inspect_content_with_dlp("Patient record: doctor@hospital.org")
        self.assertIn("EMAIL_ADDRESS", dlp_res["detected_infotypes"])
        self.assertTrue(len(dlp_res["findings_summary"]) > 0)


if __name__ == "__main__":
    unittest.main()
