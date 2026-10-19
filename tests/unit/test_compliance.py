"""Unit tests for 5-Item Regulatory Checklist and Gemini Document Scanner."""

import asyncio
import sys
from types import ModuleType
from unittest.mock import MagicMock

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
from backend.app.api.v1.compliance import (
    evaluate_onboarding_gate,
    get_compliance_horizons,
    get_room_compliance,
    scan_room_compliance,
)
from backend.app.models.compliance import (
    GateDecision,
    OnboardingGateRequest,
    RegulatoryItemStatus,
    RegulatoryItemType,
    RoomOverallCompliance,
)
from backend.app.services.compliance import ComplianceService, get_compliance_service
from scripts.provisioning.provision_storage import provision_storage


class TestComplianceService(unittest.TestCase):
    """Test suite for Gemini scanner, regulatory checklist, and onboarding gate."""

    @classmethod
    def setUpClass(cls):
        """Provision local approval documents before running tests."""
        provision_storage(dry_run=True)
        cls.service = get_compliance_service()

    def test_active_room_compliance_summary(self):
        """Verify active room rr-oncology-01 has all 5 valid prerequisite items."""
        summary = self.service.get_room_compliance("rr-oncology-01")
        self.assertEqual(summary.room_id, "rr-oncology-01")
        self.assertEqual(summary.overall_status, RoomOverallCompliance.COMPLIANT)
        self.assertEqual(len(summary.items), 5)

        for ptype in RegulatoryItemType:
            self.assertIn(ptype.value, summary.items)
            item = summary.items[ptype.value]
            self.assertEqual(item.status, RegulatoryItemStatus.APPROVED)
            self.assertTrue(item.is_valid)
            self.assertIsNotNone(item.days_remaining)
            self.assertGreater(item.days_remaining, 0)

    def test_active_room_scan_execution(self):
        """Verify Mode 1 ongoing fleet scan extracts metadata and maintains ACTIVE IAM state."""
        result = self.service.scan_room_compliance("rr-oncology-01")
        self.assertEqual(result.room_id, "rr-oncology-01")
        self.assertEqual(result.scanned_documents_count, 5)
        self.assertEqual(result.new_iam_state, "ACTIVE")

    def test_missing_document_onboarding_gate_block(self):
        """Verify Mode 2 onboarding gate blocks rr-immunology-05 due to missing Data Transfer sign-off."""
        req = OnboardingGateRequest(request_id="rr-immunology-05")
        resp = self.service.evaluate_onboarding_gate(req)

        self.assertEqual(resp.request_id, "rr-immunology-05")
        self.assertEqual(resp.gate_decision, GateDecision.GATE_BLOCKED)
        self.assertIn("Data_Transfer", resp.missing_items)
        self.assertEqual(resp.items["Data_Transfer"].status, RegulatoryItemStatus.MISSING)
        self.assertFalse(resp.items["Data_Transfer"].is_valid)

    def test_expired_document_onboarding_gate_block(self):
        """Verify Mode 2 onboarding gate blocks rr-pediatrics-06 due to expired Helsinki IRB approval."""
        req = OnboardingGateRequest(request_id="rr-pediatrics-06")
        resp = self.service.evaluate_onboarding_gate(req)

        self.assertEqual(resp.request_id, "rr-pediatrics-06")
        self.assertEqual(resp.gate_decision, GateDecision.GATE_BLOCKED)
        self.assertIn("Helsinki_IRB", resp.expired_items)
        self.assertEqual(resp.items["Helsinki_IRB"].status, RegulatoryItemStatus.EXPIRED)
        self.assertFalse(resp.items["Helsinki_IRB"].is_valid)

    def test_scan_triggers_downgrade_on_compliance_failure(self):
        """Verify Mode 1 scan triggers soft-downgrade when an active room loses compliance."""
        result = self.service.scan_room_compliance("rr-pediatrics-06")
        self.assertIn(result.new_iam_state, ["SOFT_DOWNGRADED", "ACTIVE"])
        self.assertIn(result.items["Helsinki_IRB"].status, [RegulatoryItemStatus.EXPIRED, RegulatoryItemStatus.MISSING])

    def test_horizon_report_generation(self):
        """Verify fleet-wide compliance horizon report aggregates forecasting buckets."""
        report = self.service.get_horizon_report()
        self.assertIsInstance(report.expiring_30_days, list)
        self.assertIsInstance(report.expiring_60_days, list)
        self.assertIsInstance(report.expiring_90_days, list)

    def test_api_room_compliance_controller(self):
        """Verify get_room_compliance API controller returns valid summary."""
        res = asyncio.run(get_room_compliance("rr-oncology-01", service=self.service))
        self.assertEqual(res.room_id, "rr-oncology-01")
        self.assertEqual(res.overall_status, RoomOverallCompliance.COMPLIANT)
        self.assertEqual(len(res.items), 5)

    def test_api_room_scan_controller(self):
        """Verify scan_room_compliance API controller executes live scan."""
        res = asyncio.run(scan_room_compliance("rr-oncology-01", service=self.service))
        self.assertEqual(res.room_id, "rr-oncology-01")
        self.assertEqual(res.scanned_documents_count, 5)

    def test_api_onboarding_gate_blocked_controller(self):
        """Verify evaluate_onboarding_gate API controller blocks non-compliant requests."""
        res = asyncio.run(evaluate_onboarding_gate("rr-immunology-05", service=self.service))
        self.assertEqual(res.gate_decision, GateDecision.GATE_BLOCKED)
        self.assertIn("Data_Transfer", res.missing_items)

    def test_api_horizons_controller(self):
        """Verify get_compliance_horizons API controller returns fleet forecast."""
        res = asyncio.run(get_compliance_horizons(service=self.service))
        self.assertIsInstance(res.expiring_30_days, list)
        self.assertIsInstance(res.expiring_60_days, list)
        self.assertIsInstance(res.expiring_90_days, list)


    def test_all_six_room_structures(self):
        """Verify all 6 room document sets adhere to test specifications."""
        active_rooms = ["rr-oncology-01", "rr-genomics-02", "rr-cardio-03", "rr-neurology-04"]
        for rid in active_rooms:
            summary = self.service.get_room_compliance(rid)
            self.assertEqual(summary.overall_status, RoomOverallCompliance.COMPLIANT, f"{rid} should be COMPLIANT")
            self.assertEqual(len(summary.items), 5)
            for item in summary.items.values():
                self.assertTrue(item.is_valid, f"{rid} {item.item_type} should be valid")

        # rr-immunology-05 missing Data_Transfer
        imm_summary = self.service.get_room_compliance("rr-immunology-05")
        self.assertEqual(imm_summary.overall_status, RoomOverallCompliance.INCOMPLETE)
        self.assertEqual(imm_summary.items["Data_Transfer"].status, RegulatoryItemStatus.MISSING)

        # rr-pediatrics-06 expired Helsinki_IRB
        ped_summary = self.service.get_room_compliance("rr-pediatrics-06")
        self.assertEqual(ped_summary.overall_status, RoomOverallCompliance.NON_COMPLIANT)
        self.assertEqual(ped_summary.items["Helsinki_IRB"].status, RegulatoryItemStatus.EXPIRED)

    def test_mode1_soft_downgrade_and_reactivate(self):
        """Verify Mode 1 triggers soft-downgrade on non-compliant active room and reactivation on compliance."""
        # Simulate room rr-oncology-01 scan maintaining ACTIVE
        scan_active = self.service.scan_room_compliance("rr-oncology-01")
        self.assertEqual(scan_active.new_iam_state, "ACTIVE")

        # Mock previous state as SOFT_DOWNGRADED and verify compliance scan reactivates it
        original_get_room = self.service.fleet_service.get_room
        original_reactivate = self.service.fleet_service.reactivate_room
        try:
            mock_room = original_get_room("rr-oncology-01")
            if mock_room:
                mock_room.status = "SOFT_DOWNGRADED"
                self.service.fleet_service.get_room = lambda rid: mock_room
                self.service.fleet_service.reactivate_room = lambda rid: True
                scan_reactivate = self.service.scan_room_compliance("rr-oncology-01")
                self.assertEqual(scan_reactivate.action_taken, "REACTIVATED")
                self.assertEqual(scan_reactivate.new_iam_state, "ACTIVE")
        finally:
            self.service.fleet_service.get_room = original_get_room
            self.service.fleet_service.reactivate_room = original_reactivate

    def test_mode2_onboarding_gate_does_not_alter_iam(self):
        """Verify Mode 2 evaluates requests without mutating any fleet IAM roles."""
        fleet = self.service.fleet_service
        initial_states = {r.room_id: r.status for r in fleet.list_rooms()}

        # Evaluate various Mode 2 gate requests
        self.service.evaluate_onboarding_gate(OnboardingGateRequest(request_id="rr-oncology-01"))
        self.service.evaluate_onboarding_gate(OnboardingGateRequest(request_id="rr-immunology-05"))
        self.service.evaluate_onboarding_gate(OnboardingGateRequest(request_id="rr-pediatrics-06"))

        post_states = {r.room_id: r.status for r in fleet.list_rooms()}
        self.assertEqual(initial_states, post_states, "Mode 2 must NOT mutate room IAM states")

    def test_mode2_gate_passed_on_valid_room(self):
        """Verify Mode 2 onboarding gate passes valid room."""
        req = OnboardingGateRequest(request_id="rr-oncology-01")
        resp = self.service.evaluate_onboarding_gate(req)
        self.assertEqual(resp.gate_decision, GateDecision.GATE_PASSED)
        self.assertEqual(len(resp.missing_items), 0)
        self.assertEqual(len(resp.expired_items), 0)

    def test_bigquery_telemetry_checklist_data_generation(self):
        """Verify BigQuery hub telemetry checklist data structure."""
        from scripts.provisioning.provision_bigquery import generate_hub_telemetry_data, load_topology
        topology = load_topology()
        telemetry = generate_hub_telemetry_data(topology)
        self.assertIn("ops_regulatory_checklist", telemetry)
        checklist = telemetry["ops_regulatory_checklist"]
        self.assertGreater(len(checklist), 0)
        for row in checklist:
            self.assertIn("item_id", row)
            self.assertIn("room_id", row)
            self.assertIn("item_type", row)
            self.assertIn("status", row)
            self.assertIn("expiration_date", row)


if __name__ == "__main__":
    unittest.main()

