"""
Unit tests for Cloud Infrastructure, Buckets & Environment Management
"""

import unittest
from unittest.mock import MagicMock, patch
from backend.app.models.infrastructure import (
    StorageBucketItem,
    VpcNetworkItem,
    SharedDatasetItem,
    NotebookRuntimeTemplate,
    InfrastructureOverviewResponse,
    BucketLinkRequest,
    BucketDetachRequest
)
from backend.app.services.infrastructure import InfrastructureService, NOTEBOOK_TEMPLATES


class TestInfrastructureService(unittest.TestCase):

    @patch("backend.app.services.infrastructure.storage.Client")
    @patch("backend.app.services.infrastructure.bigquery.Client")
    def setUp(self, mock_bq, mock_storage):
        self.mock_bq = mock_bq.return_value
        self.mock_storage = mock_storage.return_value
        self.service = InfrastructureService()

    def test_notebook_templates_structure(self):
        """Verifies predefined notebook runtime templates exist and have required specs."""
        self.assertGreaterEqual(len(NOTEBOOK_TEMPLATES), 4)
        for tpl in NOTEBOOK_TEMPLATES:
            self.assertTrue(tpl.template_id.startswith("tpl-"))
            self.assertGreater(tpl.vcpus, 0)
            self.assertGreater(tpl.ram_gb, 0)
            self.assertGreater(tpl.boot_disk_gb, 0)
            self.assertTrue(
                "py310" in tpl.container_image or "r-base" in tpl.container_image,
                "Container should specify valid image"
            )
            self.assertGreaterEqual(len(tpl.preinstalled_libraries), 3)

    def test_vpc_topology(self):
        """Verifies spoke VPC networks and security perimeter mappings."""
        vpcs = self.service._get_vpc_topology()
        self.assertEqual(len(vpcs), 4)
        room_ids = {v.room_id for v in vpcs}
        self.assertEqual(room_ids, {"rr-oncology-01", "rr-genomics-02", "rr-cardio-03", "rr-neurology-04"})
        for v in vpcs:
            self.assertTrue(v.private_google_access)
            self.assertIn("me-west1", v.region)

    def test_shared_datasets(self):
        """Verifies shared clinical and reference dataset schemas."""
        datasets = self.service._get_shared_datasets()
        self.assertEqual(len(datasets), 2)
        dataset_ids = [d.dataset_id for d in datasets]
        self.assertIn("hub_shared_clinical", dataset_ids)
        self.assertIn("hub_shared_reference", dataset_ids)

        for d in datasets:
            self.assertEqual(d.authorization_type, "AUTHORIZED_DATASET")
            self.assertGreaterEqual(len(d.tables), 2)
            self.assertEqual(len(d.subscribed_rooms), 4)

    def test_link_and_detach_bucket(self):
        """Tests linking and detaching storage buckets."""
        link_res = self.service.link_storage_bucket("rr-oncology-01", "custom-cohort-bucket", "INBOUND")
        self.assertEqual(link_res["status"], "SUCCESS")
        self.assertEqual(link_res["room_id"], "rr-oncology-01")

        detach_res = self.service.detach_storage_bucket("rr-oncology-01", "custom-cohort-bucket")
        self.assertEqual(detach_res["status"], "SUCCESS")
        self.assertEqual(detach_res["room_id"], "rr-oncology-01")


if __name__ == "__main__":
    unittest.main()
