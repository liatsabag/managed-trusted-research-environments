"""Unit tests for Fleet Registry & Room Governance Service and Models."""

import unittest
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
from backend.app.services.fleet import FleetGovernanceService


class TestFleetGovernanceService(unittest.TestCase):
    """Test suite for FleetGovernanceService business logic."""

    def setUp(self):
        self.service = FleetGovernanceService()

    def test_list_rooms(self):
        """Verify dynamic loading of all 4 research rooms with compliance and package info."""
        rooms = self.service.list_rooms()
        self.assertEqual(len(rooms), 4)
        room_ids = [r.room_id for r in rooms]
        self.assertIn("rr-oncology-01", room_ids)
        self.assertIn("rr-genomics-02", room_ids)
        self.assertIn("rr-cardio-03", room_ids)
        self.assertIn("rr-neurology-04", room_ids)

        for room in rooms:
            self.assertIsInstance(room, ResearchRoomSummary)
            self.assertIsNotNone(room.compliance)
            self.assertGreater(room.packages_count, 0)
            self.assertGreater(room.researcher_count, 0)
            self.assertIn(room.health_status, ["HEALTHY", "DOWNGRADED"])

    def test_get_room_detail(self):
        """Verify comprehensive room detail retrieval."""
        room = self.service.get_room("rr-oncology-01")
        self.assertIsNotNone(room)
        self.assertIsInstance(room, ResearchRoomDetail)
        self.assertEqual(room.room_id, "rr-oncology-01")
        self.assertEqual(room.institute_id, "inst-mskcc")
        self.assertEqual(room.spoke_project_id, "gcp-rr-spoke-oncology-01")
        self.assertEqual(len(room.researchers), 2)
        self.assertEqual(room.inbound_bucket, "gs://rr-oncology-01-inbound")
        self.assertEqual(room.export_bucket, "gs://rr-oncology-01-export")
        self.assertEqual(room.vpc_name, "vpc-spoke-oncology-01")
        self.assertEqual(room.subnet_name, "sb-spoke-oncology-01")
        self.assertEqual(room.template_id, "tpl-oncology-default")

    def test_dua_compliance_evaluation(self):
        """Verify compliance evaluation logic for valid and expired certificates."""
        # Test expired IRB
        expired = self.service._evaluate_dua_compliance("2020-01-01", "2028-01-01", "ACTIVE")
        self.assertFalse(expired.is_helsinki_valid)
        self.assertEqual(expired.compliance_level, "EXPIRED")
        self.assertTrue(expired.requires_action)

        # Test active valid
        valid = self.service._evaluate_dua_compliance("2028-01-01", "2028-01-01", "ACTIVE")
        self.assertTrue(valid.is_helsinki_valid)
        self.assertTrue(valid.is_dua_valid)
        self.assertEqual(valid.compliance_level, "COMPLIANT")
        self.assertFalse(valid.requires_action)

        # Test soft-downgraded room
        downgraded = self.service._evaluate_dua_compliance("2028-01-01", "2028-01-01", "SOFT_DOWNGRADED")
        self.assertEqual(downgraded.compliance_level, "NON_COMPLIANT")
        self.assertTrue(downgraded.requires_action)

    def test_downgrade_and_reactivate_lifecycle(self):
        """Verify IAM downgrade and reactivation toggling."""
        # Downgrade rr-oncology-01
        res_down = self.service.downgrade_room("rr-oncology-01", DowngradeRequest(reason="Audit check"))
        self.assertIsNotNone(res_down)
        self.assertIsInstance(res_down, RoomActionResponse)
        self.assertTrue(res_down.success)
        self.assertEqual(res_down.new_status, "SOFT_DOWNGRADED")
        self.assertGreater(len(res_down.affected_researchers), 0)

        # Check room state in BigQuery
        room_down = self.service.get_room("rr-oncology-01")
        self.assertEqual(room_down.status, "SOFT_DOWNGRADED")
        for res in room_down.researchers:
            self.assertEqual(res.access_state, "DOWNGRADED_READONLY")

        # Reactivate rr-oncology-01
        res_up = self.service.reactivate_room("rr-oncology-01")
        self.assertIsNotNone(res_up)
        self.assertTrue(res_up.success)
        self.assertEqual(res_up.new_status, "ACTIVE")

        # Check room state restored
        room_up = self.service.get_room("rr-oncology-01")
        self.assertEqual(room_up.status, "ACTIVE")
        for res in room_up.researchers:
            self.assertEqual(res.access_state, "ACTIVE")

    def test_get_room_packages(self):
        """Verify room packages, notebooks, and dataset retrieval."""
        pkgs_data = self.service.get_room_packages("rr-oncology-01")
        self.assertIsNotNone(pkgs_data)
        self.assertIn("shared_dataset_subscriptions", pkgs_data)
        self.assertIn("local_dataset", pkgs_data)
        self.assertIn("notebooks", pkgs_data)
        self.assertIn("installed_packages", pkgs_data)
        self.assertGreater(len(pkgs_data["installed_packages"]), 5)

    def test_list_institutes(self):
        """Verify retrieval of partner research institutes and room affiliations."""
        institutes = self.service.list_institutes()
        self.assertEqual(len(institutes), 4)
        for inst in institutes:
            self.assertIsInstance(inst, InstituteSummary)
        inst_map = {inst.institute_id: inst for inst in institutes}
        self.assertIn("inst-mskcc", inst_map)
        self.assertEqual(inst_map["inst-mskcc"].name, "Memorial Sloan Kettering Research Institute")
        self.assertIn("rr-oncology-01", inst_map["inst-mskcc"].rooms)

    def test_get_single_institute(self):
        """Verify retrieval of a single institute by ID."""
        inst = self.service.get_institute("inst-mskcc")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.name, "Memorial Sloan Kettering Research Institute")
        self.assertIn("rr-oncology-01", inst.rooms)

    def test_add_researcher_stub(self):
        """Verify safe stub provisioning of a researcher."""
        res = self.service.add_researcher_stub("rr-oncology-01", "new.scientist@mskcc.org", "Data Scientist")
        self.assertIsInstance(res, AddResearcherResponse)
        self.assertEqual(res.room_id, "rr-oncology-01")
        self.assertEqual(res.researcher_email, "new.scientist@mskcc.org")
        self.assertEqual(res.status, "PROVISIONED_STUB")


if __name__ == "__main__":
    unittest.main()
