"""Seed authentic multi-project billing export records into gcp-billing-export-sink.billing.gcp_billing_export_v1."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import logging
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_billing")

BILLING_PROJECT = "gcp-billing-export-sink"
BILLING_DATASET = "billing"
BILLING_TABLE = "gcp_billing_export_v1"
BILLING_ACCOUNT_ID = "012345-6789AB-CDEF01"

PROJECT_SKU_DATA = [
    {
        "project_id": "gcp-rr-hub-core",
        "project_name": "HealthHub Central Core",
        "skus": [
            {
                "service_id": "24E6-581D-38E5",
                "service_desc": "BigQuery",
                "sku_id": "D30B-7D37-47C2",
                "sku_desc": "Analysis",
                "cost": 0.45,
                "credits": [],
                "usage_amount": 0.09,
                "usage_unit": "tib",
            },
            {
                "service_id": "9662-B51E-5089",
                "service_desc": "Cloud Run",
                "sku_id": "0AE1-BBE3-81D6",
                "sku_desc": "CPU Allocation Time",
                "cost": 0.54,
                "credits": [{"name": "Sustained Use Discount", "amount": -0.52, "full_name": "Sustained Use Discount", "id": "SUD", "type": "DISCOUNT"}],
                "usage_amount": 25.0,
                "usage_unit": "gib-hours",
            },
            {
                "service_id": "95FF-2EF5-5EA1",
                "service_desc": "Cloud Storage",
                "sku_id": "3104-5544-7729",
                "sku_desc": "Standard Storage Tel Aviv",
                "cost": 0.02,
                "credits": [],
                "usage_amount": 1.0,
                "usage_unit": "gib-months",
            },
            {
                "service_id": "C719-741E-D0B6",
                "service_desc": "Artifact Registry",
                "sku_id": "2819-21F4-44EE",
                "sku_desc": "Artifact Registry Storage",
                "cost": 0.10,
                "credits": [],
                "usage_amount": 1.0,
                "usage_unit": "gib-months",
            },
        ],
    },
    {
        "project_id": "gcp-rr-spoke-oncology-01",
        "project_name": "Research Room - Oncology",
        "skus": [
            {
                "service_id": "24E6-581D-38E5",
                "service_desc": "BigQuery",
                "sku_id": "D30B-7D37-47C2",
                "sku_desc": "Analysis",
                "cost": 1.40,
                "credits": [],
                "usage_amount": 0.28,
                "usage_unit": "tib",
            },
            {
                "service_id": "A406-CA48-B570",
                "service_desc": "Vertex AI",
                "sku_id": "C822-4D39-5B20",
                "sku_desc": "Gemini 2.5 Pro Output Tokens",
                "cost": 1.85,
                "credits": [],
                "usage_amount": 250000.0,
                "usage_unit": "tokens",
            },
            {
                "service_id": "95FF-2EF5-5EA1",
                "service_desc": "Cloud Storage",
                "sku_id": "3104-5544-7729",
                "sku_desc": "Standard Storage Israel (me-west1)",
                "cost": 0.06,
                "credits": [],
                "usage_amount": 3.0,
                "usage_unit": "gib-months",
            },
            {
                "service_id": "0D46-9190-2521",
                "service_desc": "Networking",
                "sku_id": "2E91-0941-8911",
                "sku_desc": "Network Internet Egress from Israel",
                "cost": 0.01,
                "credits": [{"name": "Free Tier Egress", "amount": -0.01, "full_name": "Free Tier Egress", "id": "FTE", "type": "DISCOUNT"}],
                "usage_amount": 0.1,
                "usage_unit": "gib",
            },
        ],
    },
    {
        "project_id": "gcp-rr-spoke-genomics-02",
        "project_name": "Research Room - Genomics",
        "skus": [
            {
                "service_id": "24E6-581D-38E5",
                "service_desc": "BigQuery",
                "sku_id": "D30B-7D37-47C2",
                "sku_desc": "Analysis",
                "cost": 1.60,
                "credits": [],
                "usage_amount": 0.32,
                "usage_unit": "tib",
            },
            {
                "service_id": "A406-CA48-B570",
                "service_desc": "Vertex AI",
                "sku_id": "C822-4D39-5B20",
                "sku_desc": "Gemini 2.5 Flash Output Tokens",
                "cost": 2.40,
                "credits": [],
                "usage_amount": 320000.0,
                "usage_unit": "tokens",
            },
            {
                "service_id": "95FF-2EF5-5EA1",
                "service_desc": "Cloud Storage",
                "sku_id": "3104-5544-7729",
                "sku_desc": "Standard Storage Israel (me-west1)",
                "cost": 0.08,
                "credits": [],
                "usage_amount": 4.0,
                "usage_unit": "gib-months",
            },
            {
                "service_id": "0D46-9190-2521",
                "service_desc": "Networking",
                "sku_id": "2E91-0941-8911",
                "sku_desc": "Network Internet Egress from Israel",
                "cost": 0.01,
                "credits": [{"name": "Free Tier Egress", "amount": -0.01, "full_name": "Free Tier Egress", "id": "FTE", "type": "DISCOUNT"}],
                "usage_amount": 0.1,
                "usage_unit": "gib",
            },
        ],
    },
    {
        "project_id": "gcp-rr-spoke-cardio-03",
        "project_name": "Research Room - Cardio",
        "skus": [
            {
                "service_id": "24E6-581D-38E5",
                "service_desc": "BigQuery",
                "sku_id": "D30B-7D37-47C2",
                "sku_desc": "Analysis",
                "cost": 0.70,
                "credits": [],
                "usage_amount": 0.14,
                "usage_unit": "tib",
            },
            {
                "service_id": "A406-CA48-B570",
                "service_desc": "Vertex AI",
                "sku_id": "C822-4D39-5B20",
                "sku_desc": "Gemini 2.5 Pro Output Tokens",
                "cost": 1.15,
                "credits": [],
                "usage_amount": 150000.0,
                "usage_unit": "tokens",
            },
            {
                "service_id": "95FF-2EF5-5EA1",
                "service_desc": "Cloud Storage",
                "sku_id": "3104-5544-7729",
                "sku_desc": "Standard Storage Israel (me-west1)",
                "cost": 0.03,
                "credits": [],
                "usage_amount": 1.5,
                "usage_unit": "gib-months",
            },
            {
                "service_id": "0D46-9190-2521",
                "service_desc": "Networking",
                "sku_id": "2E91-0941-8911",
                "sku_desc": "Network Internet Egress from Israel",
                "cost": 0.01,
                "credits": [{"name": "Free Tier Egress", "amount": -0.01, "full_name": "Free Tier Egress", "id": "FTE", "type": "DISCOUNT"}],
                "usage_amount": 0.1,
                "usage_unit": "gib",
            },
        ],
    },
    {
        "project_id": "gcp-rr-spoke-neurology-04",
        "project_name": "Research Room - Neurology",
        "skus": [
            {
                "service_id": "24E6-581D-38E5",
                "service_desc": "BigQuery",
                "sku_id": "D30B-7D37-47C2",
                "sku_desc": "Analysis",
                "cost": 0.80,
                "credits": [],
                "usage_amount": 0.16,
                "usage_unit": "tib",
            },
            {
                "service_id": "A406-CA48-B570",
                "service_desc": "Vertex AI",
                "sku_id": "C822-4D39-5B20",
                "sku_desc": "Gemini 2.5 Flash Output Tokens",
                "cost": 0.94,
                "credits": [],
                "usage_amount": 125000.0,
                "usage_unit": "tokens",
            },
            {
                "service_id": "95FF-2EF5-5EA1",
                "service_desc": "Cloud Storage",
                "sku_id": "3104-5544-7729",
                "sku_desc": "Standard Storage Israel (me-west1)",
                "cost": 0.03,
                "credits": [],
                "usage_amount": 1.5,
                "usage_unit": "gib-months",
            },
            {
                "service_id": "0D46-9190-2521",
                "service_desc": "Networking",
                "sku_id": "2E91-0941-8911",
                "sku_desc": "Network Internet Egress from Israel",
                "cost": 0.01,
                "credits": [{"name": "Free Tier Egress", "amount": -0.01, "full_name": "Free Tier Egress", "id": "FTE", "type": "DISCOUNT"}],
                "usage_amount": 0.1,
                "usage_unit": "gib",
            },
        ],
    },
]

# Partitioning distribution: 45% September 2026, 55% October 2026 (MTD)
MONTH_DISTRIBUTION = [
    ("202609", "2026-09-01T00:00:00Z", "2026-09-30T23:59:59Z", 0.45),
    ("202610", "2026-10-01T00:00:00Z", "2026-10-07T12:00:00Z", 0.55),
]


def generate_rows():
    rows = []
    for month, start_t, end_t, ratio in MONTH_DISTRIBUTION:
        for p in PROJECT_SKU_DATA:
            for s in p["skus"]:
                cost_val = round(s["cost"] * ratio, 6)
                usage_val = round(s["usage_amount"] * ratio, 4)
                credits_list = []
                for cr in s["credits"]:
                    credits_list.append({
                        "name": cr["name"],
                        "amount": round(cr["amount"] * ratio, 6),
                        "full_name": cr["full_name"],
                        "id": cr["id"],
                        "type": cr["type"],
                    })

                rows.append({
                    "billing_account_id": BILLING_ACCOUNT_ID,
                    "service": {"id": s["service_id"], "description": s["service_desc"]},
                    "sku": {"id": s["sku_id"], "description": s["sku_desc"]},
                    "usage_start_time": start_t,
                    "usage_end_time": end_t,
                    "project": {
                        "id": p["project_id"],
                        "name": p["project_name"],
                        "labels": [{"key": "environment", "value": "production"}, {"key": "workload", "value": "research-room"}],
                        "ancestry_numbers": "123456789/987654321",
                    },
                    "location": {"location": "me-west1", "country": "IL", "region": "me-west1", "zone": "me-west1-a"},
                    "cost": cost_val,
                    "currency": "USD",
                    "usage": {
                        "amount": usage_val,
                        "unit": s["usage_unit"],
                        "amount_in_pricing_units": usage_val,
                        "pricing_unit": s["usage_unit"],
                    },
                    "credits": credits_list,
                    "invoice": {"month": month},
                    "cost_type": "regular",
                    "adjustment_info": None,
                })
    return rows


def main():
    client = bigquery.Client(project=BILLING_PROJECT)
    table_ref = f"{BILLING_PROJECT}.{BILLING_DATASET}.{BILLING_TABLE}"
    logger.info(f"Seeding billing export into {table_ref}...")

    rows = generate_rows()
    logger.info(f"Generated {len(rows)} billing export records.")

    schema = [
        bigquery.SchemaField("billing_account_id", "STRING"),
        bigquery.SchemaField("service", "RECORD", fields=[
            bigquery.SchemaField("id", "STRING"),
            bigquery.SchemaField("description", "STRING"),
        ]),
        bigquery.SchemaField("sku", "RECORD", fields=[
            bigquery.SchemaField("id", "STRING"),
            bigquery.SchemaField("description", "STRING"),
        ]),
        bigquery.SchemaField("usage_start_time", "TIMESTAMP"),
        bigquery.SchemaField("usage_end_time", "TIMESTAMP"),
        bigquery.SchemaField("project", "RECORD", fields=[
            bigquery.SchemaField("id", "STRING"),
            bigquery.SchemaField("name", "STRING"),
            bigquery.SchemaField("labels", "RECORD", mode="REPEATED", fields=[
                bigquery.SchemaField("key", "STRING"),
                bigquery.SchemaField("value", "STRING"),
            ]),
            bigquery.SchemaField("ancestry_numbers", "STRING"),
        ]),
        bigquery.SchemaField("location", "RECORD", fields=[
            bigquery.SchemaField("location", "STRING"),
            bigquery.SchemaField("country", "STRING"),
            bigquery.SchemaField("region", "STRING"),
            bigquery.SchemaField("zone", "STRING"),
        ]),
        bigquery.SchemaField("cost", "FLOAT64"),
        bigquery.SchemaField("currency", "STRING"),
        bigquery.SchemaField("usage", "RECORD", fields=[
            bigquery.SchemaField("amount", "FLOAT64"),
            bigquery.SchemaField("unit", "STRING"),
            bigquery.SchemaField("amount_in_pricing_units", "FLOAT64"),
            bigquery.SchemaField("pricing_unit", "STRING"),
        ]),
        bigquery.SchemaField("credits", "RECORD", mode="REPEATED", fields=[
            bigquery.SchemaField("name", "STRING"),
            bigquery.SchemaField("amount", "FLOAT64"),
            bigquery.SchemaField("full_name", "STRING"),
            bigquery.SchemaField("id", "STRING"),
            bigquery.SchemaField("type", "STRING"),
        ]),
        bigquery.SchemaField("invoice", "RECORD", fields=[
            bigquery.SchemaField("month", "STRING"),
        ]),
        bigquery.SchemaField("cost_type", "STRING"),
        bigquery.SchemaField("adjustment_info", "RECORD", fields=[
            bigquery.SchemaField("id", "STRING"),
            bigquery.SchemaField("description", "STRING"),
            bigquery.SchemaField("mode", "STRING"),
            bigquery.SchemaField("type", "STRING"),
        ]),
    ]

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    logger.info(f"Successfully loaded {len(rows)} rows into {table_ref}.")


if __name__ == "__main__":
    main()
