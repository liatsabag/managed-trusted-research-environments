"""Unit tests for GCP Research Room Fleet Bootstrap and Schema Generation."""

import json
import unittest
from pathlib import Path
from scripts.provisioning.bootstrap_gcp import run_bootstrap
from scripts.provisioning.provision_bigquery import load_sql_ddls, provision_bigquery
from scripts.provisioning.provision_identity import provision_identity
from scripts.provisioning.provision_notebooks import provision_notebooks
from scripts.provisioning.provision_storage import provision_storage


class TestBootstrap(unittest.TestCase):
    """Test suite for Batch 1 provisioning modules."""

    def test_topology_loading(self):
        """Verify fleet_topology.json contains all 4 rooms, 8 researchers, and required configs."""
        topo_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "fixtures" / "fleet_topology.json"
        self.assertTrue(topo_path.exists())
        with open(topo_path, "r", encoding="utf-8") as f:
            topo = json.load(f)
        self.assertEqual(len(topo["research_rooms"]), 4)
        all_res = [r for rm in topo["research_rooms"] for r in rm["researchers"]]
        self.assertEqual(len(all_res), 8)

    def test_sql_ddl_loading(self):
        """Verify all 5 SQL DDL files are present and valid."""
        ddls = load_sql_ddls()
        expected_files = [
            "schema_hub_shared.sql",
            "schema_registry.sql",
            "schema_spoke_local.sql",
            "schema_telemetry.sql",
            "view_billing_export.sql",
        ]
        for ef in expected_files:
            self.assertIn(ef, ddls)
            self.assertTrue(len(ddls[ef].strip()) > 0)

    def test_identity_provisioning(self):
        """Verify identity provisioning creates 8 users, 4 groups, and IAM bindings."""
        res = provision_identity(dry_run=True)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["users_count"], 8)
        self.assertEqual(res["groups_count"], 4)
        self.assertEqual(res["registry_records_count"], 8)

    def test_bigquery_provisioning(self):
        """Verify BigQuery provisioning generates all tables matching target row counts."""
        res = provision_bigquery(dry_run=True)
        self.assertGreater(res["total_rows_generated"], 9000)
        self.assertEqual(len(res["datasets"]), 8)
        self.assertIn("hub_shared_clinical", res["datasets"])
        self.assertIn("spoke_local_oncology", res["datasets"])

    def test_storage_provisioning(self):
        """Verify storage provisioning sets up 8 dual-buckets, 13 inbound files, and 4 quarantine files."""
        res = provision_storage(dry_run=True)
        self.assertEqual(len(res["buckets_provisioned"]), 8)
        self.assertEqual(len(res["file_manifest"]), 17)

    def test_notebooks_provisioning(self):
        """Verify 8 valid Jupyter notebooks are generated."""
        res = provision_notebooks(dry_run=True)
        self.assertEqual(res["notebooks_created"], 8)
        self.assertEqual(len(res["room_notebooks"]), 4)

    def test_full_bootstrap_run(self):
        """Verify end-to-end master bootstrap runner executes cleanly."""
        res = run_bootstrap(run_all=True, dry_run=True)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(len(res["modules_executed"]), 5)
        self.assertIn("identity", res["modules_executed"])
        self.assertIn("bigquery", res["modules_executed"])
        self.assertIn("storage", res["modules_executed"])
        self.assertIn("notebooks", res["modules_executed"])
        self.assertIn("runtimes", res["modules_executed"])


if __name__ == "__main__":
    unittest.main()
