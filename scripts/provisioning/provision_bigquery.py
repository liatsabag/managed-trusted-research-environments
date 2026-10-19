"""BigQuery provisioning and synthetic data population module."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from scripts.provisioning.provision_analytics_hub import provision_analytics_hub
from scripts.etl.data_generators import (
    generate_cardio_data,
    generate_gene_panel,
    generate_genomics_data,
    generate_icd10,
    generate_lab_ranges,
    generate_neurology_data,
    generate_omop_vocab,
    generate_oncology_data,
)

logger = logging.getLogger("provision_bigquery")


def load_topology(topology_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load fleet topology JSON specification."""
    if topology_path is None:
        topology_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sql_ddls() -> Dict[str, str]:
    """Load all SQL DDL definition files."""
    sql_dir = Path(__file__).resolve().parents[1] / "sql"
    ddls = {}
    for sql_file in sorted(sql_dir.glob("*.sql")):
        with open(sql_file, "r", encoding="utf-8") as f:
            ddls[sql_file.name] = f.read()
    return ddls


def generate_hub_registry_data(topology: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Generate registry tables data from topology."""
    institutes = topology.get("institutes", [])
    rooms, researchers, packages = [], [], []

    standard_pkgs = [("pandas", "2.2.1"), ("numpy", "1.26.4"), ("scipy", "1.12.0"), ("scikit-learn", "1.4.1.post1"), ("google-cloud-bigquery", "3.19.0"), ("google-cloud-storage", "2.14.0")]
    domain_pkgs = {
        "rr-oncology-01": [("lifelines", "0.28.0"), ("matplotlib", "3.8.3"), ("seaborn", "0.13.2")],
        "rr-genomics-02": [("biopython", "1.83"), ("cyvcf2", "0.30.28"), ("pysam", "0.22.0")],
        "rr-cardio-03": [("wfdb", "4.1.2"), ("statsmodels", "0.14.1"), ("xgboost", "2.0.3")],
        "rr-neurology-04": [("nibabel", "5.2.1"), ("nilearn", "0.10.4"), ("torch", "2.2.1")],
    }

    lead_researchers = {
        "rr-oncology-01": "res-onc-01",
        "rr-genomics-02": "res-gen-01",
        "rr-cardio-03": "res-card-01",
        "rr-neurology-04": "res-neur-01",
    }

    for r in topology.get("research_rooms", []):
        room_id = r["room_id"]
        table_count = len(r.get("local_dataset", {}).get("tables", []))
        lead_id = lead_researchers.get(room_id)
        lead_res = next((res for res in r.get("researchers", []) if res["researcher_id"] == lead_id), None)
        lead_email = lead_res["primary_email"] if lead_res else None
        budget_map = {"rr-oncology-01": 5000.0, "rr-genomics-02": 10000.0, "rr-cardio-03": 7500.0, "rr-neurology-04": 6000.0}
        budget_val = r.get("budget_limit_usd", budget_map.get(room_id, 5000.0))
        rooms.append({
            "room_id": room_id, "room_name": r["room_name"], "institute_id": r["institute_id"],
            "spoke_project_id": r["spoke_project_id"], "status": r["status"],
            "helsinki_expiry_date": r["helsinki_expiry_date"], "dua_expiry_date": r["dua_expiry_date"],
            "inbound_bucket": r["inbound_bucket"], "export_bucket": r["export_bucket"],
            "cloud_identity_group": r["cloud_identity_group"], "tables_count": table_count,
            "lead_researcher_id": lead_id,
            "lead_researcher_email": lead_email,
            "budget_limit_usd": budget_val,
            "created_at": "2026-09-24T08:00:00Z",
        })
        for res in r.get("researchers", []):
            researchers.append({
                "researcher_id": res["researcher_id"], "first_name": res["first_name"],
                "last_name": res["last_name"], "primary_email": res["primary_email"],
                "role": res["role"], "access_state": res["access_state"],
                "org_unit_path": res.get("org_unit_path", "/Researchers"), "institute_id": r["institute_id"],
                "room_id": room_id, "cloud_identity_group": r["cloud_identity_group"],
                "is_active": res["access_state"] != "SUSPENDED",
            })
        for pkg_name, pkg_ver in standard_pkgs + domain_pkgs.get(room_id, []):
            packages.append({"room_id": room_id, "runtime_id": f"runtime-{room_id}-default", "package_name": pkg_name, "package_version": pkg_ver})

    return {"reg_institutes": institutes, "reg_research_rooms": rooms, "reg_researchers": researchers, "reg_room_packages": packages}


def generate_hub_telemetry_data(topology: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Generate telemetry tables data (unified regulatory checklist, enriched room requests)."""
    checklist = []
    item_types = [
        ("Research_Protocol", "Approved Scientific Research Protocol"),
        ("Helsinki_IRB", "Helsinki Ethics Committee / IRB Approval"),
        ("Data_Transfer", "Data Transfer Committee Statutory Sign-off"),
        ("Extraction_Protocol", "De-identification & Extraction Query Protocol"),
        ("DUA", "Multi-party Data Use Agreement"),
    ]

    for room in topology.get("research_rooms", []):
        room_id = room["room_id"]
        for itype, iname in item_types:
            exp_date = room.get("helsinki_expiry_date", "2027-12-31") if itype == "Helsinki_IRB" else room.get("dua_expiry_date", "2028-04-30")
            checklist.append({
                "item_id": f"{room_id}-{itype}", "room_id": room_id, "room_type": "PROVISIONED",
                "item_type": itype, "item_name": iname, "status": "Approved", "approval_date": "2024-10-15",
                "expiration_date": exp_date, "approver_name": "HealthHub Ethics & Governance Directorate",
                "document_uri": f"gs://gcp-rr-hub-approvals/{room_id}/{itype.lower()}_approval.txt",
                "comments": "Statutory prerequisite verified and compliant.",
            })

    for req in topology.get("room_requests", []):
        room_id = req["proposed_room_id"]
        for itype, iname in item_types:
            if room_id == "rr-immunology-05" and itype == "Data_Transfer":
                checklist.append({
                    "item_id": f"{room_id}-{itype}", "room_id": room_id, "room_type": "PENDING_REQUEST",
                    "item_type": itype, "item_name": iname, "status": "MISSING", "approval_date": None,
                    "expiration_date": None, "approver_name": None,
                    "document_uri": f"gs://gcp-rr-hub-approvals/{room_id}/{itype.lower()}_approval.txt",
                    "comments": "Document missing in regulatory checklist.",
                })
            elif room_id == "rr-pediatrics-06" and itype == "Helsinki_IRB":
                checklist.append({
                    "item_id": f"{room_id}-{itype}", "room_id": room_id, "room_type": "PENDING_REQUEST",
                    "item_type": itype, "item_name": iname, "status": "EXPIRED", "approval_date": "2023-01-15",
                    "expiration_date": "2024-05-15", "approver_name": "HealthHub Ethics & Governance Directorate",
                    "document_uri": f"gs://gcp-rr-hub-approvals/{room_id}/{itype.lower()}_approval.txt",
                    "comments": "Approval expired on 2024-05-15.",
                })
            else:
                checklist.append({
                    "item_id": f"{room_id}-{itype}", "room_id": room_id, "room_type": "PENDING_REQUEST",
                    "item_type": itype, "item_name": iname, "status": "Approved", "approval_date": "2024-10-15",
                    "expiration_date": "2027-12-31", "approver_name": "HealthHub Ethics & Governance Directorate",
                    "document_uri": f"gs://gcp-rr-hub-approvals/{room_id}/{itype.lower()}_approval.txt",
                    "comments": "Statutory prerequisite verified.",
                })

    room_requests = [
        {
            "request_id": req["request_id"], "proposed_room_id": req["proposed_room_id"],
            "room_name": req["room_name"], "institute_id": req["institute_id"],
            "requested_by": req["requested_by"], "main_researcher": req.get("main_researcher", req["requested_by"]),
            "purpose_of_research": req.get("purpose_of_research", "Biomedical research study"),
            "location": req.get("location", "Institutional Research Center"),
            "expected_funds_usd": req.get("expected_funds_usd", 500000.0),
            "budget_limit_usd": req.get("budget_limit_usd", req.get("expected_funds_usd", 500000.0)),
            "expected_time_range": req.get("expected_time_range", "24 months"),
            "document_folder_uri": req["document_folder_uri"], "status": req.get("status", "PENDING_SCAN"),
            "gate_decision": req.get("gate_decision", "GATE_BLOCKED"),
            "missing_items": json.dumps(req.get("missing_items", [])),
            "expired_items": json.dumps(req.get("expired_items", [])),
            "warning_items": json.dumps(req.get("warning_items", [])),
            "summary_reason": req.get("summary_reason", "Pre-flight gate scan pending"),
        }
        for req in topology.get("room_requests", [])
    ]

    return {"ops_regulatory_checklist": checklist, "ops_room_requests": room_requests, "ops_airlock_requests": [], "ops_audit_logs": []}


def provision_bigquery(
    topology: Optional[Dict[str, Any]] = None,
    staging_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute end-to-end BigQuery dataset creation, schemas, and data loading across Hub and Spoke projects."""
    if topology is None:
        topology = load_topology()
    if staging_dir is None:
        staging_dir = Path(__file__).resolve().parent.parent / "staging" / "bigquery"

    staging_dir.mkdir(parents=True, exist_ok=True)
    hub_proj = topology.get("hub_project", {}).get("project_id", "gcp-rr-hub-core")
    region = topology.get("hub_project", {}).get("region", "me-west1")

    from google.cloud import bigquery
    bq_clients = {hub_proj: bigquery.Client(project=hub_proj, location=region)}
    for room in topology.get("research_rooms", []):
        spoke_p = room.get("spoke_project_id", hub_proj)
        if spoke_p not in bq_clients:
            bq_clients[spoke_p] = bigquery.Client(project=spoke_p, location=region)
    logger.info("Connected to live BigQuery Clients across %d projects: %s", len(bq_clients), list(bq_clients.keys()))

    ddls = load_sql_ddls()
    results: Dict[str, Any] = {"datasets": {}, "ddls_loaded": list(ddls.keys()), "total_rows_generated": 0}

    def ensure_live_dataset(proj: str, dataset_id: str):
        if proj in bq_clients:
            from google.cloud import bigquery
            dataset_ref = bigquery.DatasetReference(proj, dataset_id)
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = region
            bq_clients[proj].create_dataset(dataset, exists_ok=True)
            logger.info("Created / Verified live BigQuery dataset: %s.%s in %s", proj, dataset_id, region)

    # 1. Cleanup any invalid datasets in Hub (NO billing dataset and NO spoke local datasets in Hub)
    if hub_proj in bq_clients:
        hub_client = bq_clients[hub_proj]
        invalid_hub_datasets = ["billing", "spoke_local_oncology", "spoke_local_genomics", "spoke_local_cardio", "spoke_local_neurology"]
        for inv_ds in invalid_hub_datasets:
            try:
                hub_client.delete_dataset(inv_ds, delete_contents=True, not_found_ok=True)
                logger.info("Ensured invalid dataset '%s' is not in Hub project '%s'", inv_ds, hub_proj)
            except Exception as e:
                logger.debug("Hub cleanup notice for %s: %s", inv_ds, e)

    # 2. Pre-create valid Hub datasets
    for ds_id in ["hub_registry", "hub_telemetry", "hub_shared_clinical", "hub_shared_reference"]:
        ensure_live_dataset(hub_proj, ds_id)

    # 3. Pre-create Spoke local datasets in their respective spoke projects ONLY
    for room in topology.get("research_rooms", []):
        spoke_p = room.get("spoke_project_id", hub_proj)
        local_ds = room.get("local_dataset", {})
        ds_id = local_ds.get("dataset_id")
        if ds_id:
            ensure_live_dataset(spoke_p, ds_id)

    # 4. Execute DDLs on live BigQuery clients
    if bq_clients:
        hub_client = bq_clients[hub_proj]
        
        # Execute Registry, Telemetry, and Shared schemas on Hub
        hub_ddl_files = [
            "schema_registry.sql", "schema_telemetry.sql", "schema_hub_shared.sql",
            "curate_audit_events.sql", "finops_usage_tracking.sql", "aggregate_compute_metrics.sql",
            "view_billing_export.sql"
        ]
        for ddl_name in hub_ddl_files:
            if ddl_name in ddls:
                try:
                    logger.info("Executing DDL in live Hub BigQuery: %s", ddl_name)
                    job = hub_client.query(ddls[ddl_name])
                    job.result()
                    logger.info("DDL executed successfully: %s", ddl_name)
                except Exception as e:
                    logger.warning("Live DDL execution notice for %s on Hub: %s", ddl_name, e)

        # Execute Spoke Local schema on each spoke project
        if "schema_spoke_local.sql" in ddls:
            spoke_ddl_content = ddls["schema_spoke_local.sql"]
            for room in topology.get("research_rooms", []):
                spoke_p = room.get("spoke_project_id")
                ds_id = room.get("local_dataset", {}).get("dataset_id")
                client = bq_clients.get(spoke_p)
                if client and ds_id:
                    statements = [stmt.strip() for stmt in spoke_ddl_content.split(";") if stmt.strip()]
                    for stmt in statements:
                        if ds_id in stmt:
                            try:
                                logger.info("Executing DDL in Spoke %s BigQuery: %s", spoke_p, stmt.split("\n")[0][:60])
                                job = client.query(stmt)
                                job.result()
                            except Exception as e:
                                logger.warning("Live DDL execution notice for %s on %s: %s", ds_id, spoke_p, e)

    def load_table_truncate(proj: str, dataset_id: str, table_id: str, rows: List[Dict[str, Any]]):
        """Idempotently load table using WRITE_TRUNCATE to guarantee exact row counts."""
        client = bq_clients.get(proj)
        if not client:
            return
        from google.cloud import bigquery
        table_ref = f"{proj}.{dataset_id}.{table_id}"
        if not rows:
            # If empty rows requested, ensure table exists and is empty
            try:
                client.query(f"TRUNCATE TABLE `{table_ref}`").result()
                logger.info("Truncated table to empty: %s", table_ref)
            except Exception as e:
                logger.debug("Truncate notice for empty table %s: %s", table_ref, e)
            return

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            autodetect=False,
        )
        for attempt in range(5):
            try:
                load_job = client.load_table_from_json(rows, table_ref, job_config=job_config)
                load_job.result()  # Wait for completion
                logger.info("Successfully loaded %d rows (WRITE_TRUNCATE) into %s", len(rows), table_ref)
                break
            except Exception as exc:
                if ("404" in str(exc) or "not found" in str(exc).lower()) and attempt < 4:
                    logger.info("Table %s not ready, waiting 3s (attempt %d/5)...", table_ref, attempt + 1)
                    time.sleep(3)
                else:
                    logger.warning("Error loading data into %s: %s", table_ref, exc)
                    raise exc

    # 5. Hub Registry & Telemetry Data Generation & Loading
    reg_data = generate_hub_registry_data(topology)
    tele_data = generate_hub_telemetry_data(topology)

    for ds_name, data_map in [("hub_registry", reg_data), ("hub_telemetry", tele_data)]:
        results["datasets"][ds_name] = {}
        for tbl_name, rows in data_map.items():
            tbl_path = staging_dir / ds_name / f"{tbl_name}.json"
            tbl_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tbl_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2)
            results["datasets"][ds_name][tbl_name] = len(rows)
            results["total_rows_generated"] += len(rows)
            logger.info("Generated [%s.%s]: %d rows", ds_name, tbl_name, len(rows))

            if bq_clients:
                load_table_truncate(hub_proj, ds_name, tbl_name, rows)

    # 6. Hub Shared Datasets Generation & Loading
    shared_generators = {
        "hub_shared_clinical": {
            "icd10_catalogs": (generate_icd10, 500),
            "omop_vocabulary": (generate_omop_vocab, 800),
        },
        "hub_shared_reference": {
            "reference_gene_panel": (generate_gene_panel, 250),
            "standard_lab_ranges": (generate_lab_ranges, 150),
        },
    }
    for ds_name, tbls in shared_generators.items():
        results["datasets"][ds_name] = {}
        for tbl_name, (gen_fn, target_count) in tbls.items():
            rows = gen_fn(target_count)
            tbl_path = staging_dir / ds_name / f"{tbl_name}.json"
            tbl_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tbl_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2)
            results["datasets"][ds_name][tbl_name] = len(rows)
            results["total_rows_generated"] += len(rows)
            logger.info("Generated [%s.%s]: %d rows", ds_name, tbl_name, len(rows))

            if bq_clients:
                load_table_truncate(hub_proj, ds_name, tbl_name, rows)

    # 7. Spoke Local Datasets Generation & Loading (Strictly into Spoke projects)
    spoke_gen_map = {
        "spoke_local_oncology": generate_oncology_data,
        "spoke_local_genomics": generate_genomics_data,
        "spoke_local_cardio": generate_cardio_data,
        "spoke_local_neurology": generate_neurology_data,
    }
    for room in topology.get("research_rooms", []):
        spoke_p = room.get("spoke_project_id", hub_proj)
        local_ds = room.get("local_dataset", {})
        ds_id = local_ds.get("dataset_id")
        if ds_id and ds_id in spoke_gen_map:
            gen_fn = spoke_gen_map[ds_id]
            results["datasets"][ds_id] = {}
            for tbl in local_ds.get("tables", []):
                t_id = tbl["table_id"]
                t_count = tbl["target_row_count"]
                rows = gen_fn(t_id, t_count)
                tbl_path = staging_dir / ds_id / f"{t_id}.json"
                tbl_path.parent.mkdir(parents=True, exist_ok=True)
                with open(tbl_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2)
                results["datasets"][ds_id][t_id] = len(rows)
                results["total_rows_generated"] += len(rows)
                logger.info("Generated [%s.%s]: %d rows in spoke project %s", ds_id, t_id, len(rows), spoke_p)

                if bq_clients:
                    load_table_truncate(spoke_p, ds_id, t_id, rows)

    # 8. Provision BigQuery Analytics Hub Exchange & Linked Dataset Subscriptions
    if not dry_run:
        analytics_hub_res = provision_analytics_hub(topology, region=region)
        results["analytics_hub"] = analytics_hub_res

        # 9. Trigger initial telemetry curation and aggregation pipeline sync
        if hub_proj in bq_clients:
            hub_c = bq_clients[hub_proj]
            for proc in ["sp_sync_curated_audit_events", "sp_sync_notebook_session_metrics", "sp_sync_ai_usage_metrics", "sp_aggregate_daily_compute_metrics", "sp_rollup_monthly_usage"]:
                try:
                    hub_c.query(f"CALL `{hub_proj}.hub_telemetry.{proc}`()").result()
                except Exception as exc:
                    logger.warning("Notice executing stored procedure %s: %s", proc, exc)

    logger.info("BigQuery provisioning complete. Total rows generated: %d", results["total_rows_generated"])
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    res = provision_bigquery()
    print(json.dumps(res, indent=2, default=str))
