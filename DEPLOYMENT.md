# Zero-to-Production Deployment Runbook & Traffic Operations Manual

**GCP Multi-Tenant Trusted Research Environment (TRE) & Research Room Management System**  
*Step-by-Step Provisioning, Traffic Generation, Dynamic Cost Verification & Operations Manual*  
*Document Version:* `3.1.0 (Production Verified)`

---

## 1. Prerequisites & Pre-Flight Checklist

### 1.1 Required Tooling & Versions
* **Google Cloud SDK (`gcloud`)**: Version `480.0.0+`
* **BigQuery CLI (`bq`)**: Version `2.1.0+`
* **Python**: Version `3.10` or `3.11` with `pip` and virtual environment support
* **Docker / Cloud Build**: Container build capabilities
* **jq**: Lightweight command-line JSON processor

### 1.2 IAM Permission Requirements
The deploying identity (Deployer User or CI/CD Service Account) requires:
* `roles/resourcemanager.organizationAdmin` or `roles/resourcemanager.folderAdmin` (on folder `752086743397`)
* `roles/owner` or `roles/editor` + `roles/iam.securityAdmin` on Hub (`gcp-rr-hub-core`) and Spoke projects (`gcp-rr-spoke-*`)
* `roles/bigquery.admin` on `gcp-rr-hub-core`
* `roles/bigquery.dataViewer` on billing project `majestic-energy-353306`
* `roles/run.admin` on `gcp-rr-hub-core`
* `roles/workflows.admin` on `gcp-rr-hub-core`

### 1.3 Pre-Flight API Enablement
Execute the following command to enable all required GCP APIs across the central Hub project:

```bash
gcloud services enable \
    compute.googleapis.com \
    bigquery.googleapis.com \
    bigquerydatatransfer.googleapis.com \
    bigqueryconnection.googleapis.com \
    analyticshub.googleapis.com \
    aiplatform.googleapis.com \
    run.googleapis.com \
    workflows.googleapis.com \
    workflowexecutions.googleapis.com \
    logging.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project=gcp-rr-hub-core
```

---

## 2. Configuration & Environment Matrix

Create a `.env` file in the repository root or configure the following environment variables:

| Variable Name | Description | Default / Production Value | Required / Secret |
| :--- | :--- | :--- | :--- |
| `GCP_PROJECT_ID` | Central Hub Project ID | `gcp-rr-hub-core` | **Required** |
| `GCP_REGION` | Primary Compute & BigQuery Region | `me-west1` | **Required** |
| `ADMIN_DOMAIN` | Enterprise Cloud Identity Domain | `liatsabag.altostrat.com` | **Required** |
| `BILLING_PROJECT_ID` | GCP Project hosting Billing Export | `majestic-energy-353306` | **Required** |
| `BILLING_DATASET_ID` | BigQuery Dataset ID with Billing Export | `billing` | **Required** |
| `BILLING_EXPORT_TABLE` | Partitioned Billing Export Table Name | `gcp_billing_export_v1_017F5D_25BB78_C82332` | **Required** |
| `HUB_REGISTRY_DATASET`| Central Hub Registry Dataset | `hub_registry` | **Required** |
| `HUB_TELEMETRY_DATASET`| Central Hub Telemetry Mart Dataset | `hub_telemetry` | **Required** |
| `VERTEX_AI_MODEL` | Modern Gemini Model for DUA / Risk Scans | `gemini-3.7-flash` | **Required** |
| `VERTEX_AI_LOCATION` | Vertex AI Model Region | `me-west1` | **Required** |
| `BACKEND_API_URL` | Cloud Run Backend Service URL | `https://gcp-rr-hub-backend-468155375703.me-west1.run.app` | Auto-Generated |

---

## 3. Step-by-Step Provisioning (Strict Dependency Order)

#### Step 1: Storage Dual-Bucket Provisioning
Provisions the central approvals bucket and all room-isolated `inbound` (read-only) and `export` (write-only quarantine) buckets.

```bash
python3 scripts/provisioning/provision_storage.py
```
**Verification Command:**
```bash
gcloud storage buckets list --project=gcp-rr-hub-core --format="table(name,location)"
```

---

### Step 2: BigQuery Datasets & Tables DDL
Executes SQL scripts to create `hub_registry` catalogs, `hub_telemetry` marts, and the dynamic `view_billing_export` view.

```bash
# 1. Create Hub Registry Catalog
bq query --use_legacy_sql=false < scripts/sql/schema_registry.sql

# 2. Create Hub Telemetry Marts & Object Tables
bq query --use_legacy_sql=false < scripts/sql/schema_telemetry.sql

# 3. Create Dynamic Authorized Billing Export View
bq query --use_legacy_sql=false < scripts/sql/view_billing_export.sql

# 4. Deploy Stored Procedures
bq query --use_legacy_sql=false < scripts/sql/finops_usage_tracking.sql
bq query --use_legacy_sql=false < scripts/sql/aggregate_compute_metrics.sql
bq query --use_legacy_sql=false < scripts/sql/sp_scan_governance.sql
```
**Verification Command:**
```bash
bq ls --project_id=gcp-rr-hub-core hub_telemetry
```

---

### Step 3: BigQuery ML Connection & Vertex AI Gemini Model
Creates the BigQuery remote connection and binds the Gemini 3.7 Flash remote model for automated DUA / Helsinki regulatory scanning.

```bash
# Create Remote Connection
bq mk --connection --location=me-west1 --project_id=gcp-rr-hub-core --connection_type=CLOUD_RESOURCE gemini-connection

# Get Connection Service Account
CONNECTION_SA=$(bq show --format=json --connection gcp-rr-hub-core.me-west1.gemini-connection | jq -r '.cloudResource.serviceAccountId')

# Grant Vertex AI User to Connection Service Account
gcloud projects add-iam-policy-binding gcp-rr-hub-core \
    --member="serviceAccount:${CONNECTION_SA}" \
    --role="roles/aiplatform.user"

# Grant Storage Object Viewer on Approvals Bucket
gcloud storage buckets add-iam-policy-binding gs://gcp-rr-hub-approvals \
    --member="serviceAccount:${CONNECTION_SA}" \
    --role="roles/storage.objectViewer"
```
**Verification Command:**
```bash
bq query --use_legacy_sql=false \
    "SELECT * FROM ML.GENERATE_TEXT(MODEL \`gcp-rr-hub-core.hub_telemetry.gemini_flash_model\`, (SELECT 'Hello' AS prompt), STRUCT(50 AS max_output_tokens));"
```

---

### Step 4: BigQuery Data Transfer Service Scheduled Queries
Deploys the 15-minute curation sync and 24-hour daily rollup DTS schedules in `me-west1`.

```bash
python3 scripts/provisioning/provision_scheduled_queries.py
```
**Verification Command:**
```bash
bq ls --transfer_config --transfer_location=me-west1 --project_id=gcp-rr-hub-core
```

---

### Step 5: Cloud Logging Sinks (Cross-Project Telemetry)
Configures log router sinks in each spoke project to stream `cloudaudit_googleapis_com_data_access` into `hub_telemetry`.

```bash
python3 scripts/provisioning/provision_log_sinks.py
```
**Verification Command:**
```bash
gcloud logging sinks list --project=gcp-rr-spoke-oncology-01
```

---

### Step 6: Spoke VPC Networks & Colab Enterprise Runtimes
Provisions private VPC subnets (`10.10.x.0/24`) with `disable_public_ip = true`, Shielded VM profiles, and Colab runtime templates.

```bash
python3 scripts/provisioning/provision_runtime_templates.py
python3 scripts/provisioning/provision_notebooks.py
```
**Verification Command:**
```bash
gcloud compute networks subnets list --project=gcp-rr-spoke-oncology-01
```

---

### Step 7: BigQuery Analytics Hub Data Exchanges
Sets up governed shared dataset listings for cross-room research without direct IAM table sharing.

```bash
python3 scripts/provisioning/provision_analytics_hub.py
```
**Verification Command:**
```bash
gcloud alpha bq analytics-hub data-exchanges list --location=me-west1 --project=gcp-rr-hub-core
```

---

### Step 8: Cloud Run Backend & Frontend Deployment
Builds container images using Cloud Build and deploys to Cloud Run in `me-west1`.

```bash
# 1. Deploy Backend API
gcloud builds submit backend --tag gcr.io/gcp-rr-hub-core/backend:latest --project=gcp-rr-hub-core
gcloud run deploy gcp-rr-hub-backend \
    --image gcr.io/gcp-rr-hub-core/backend:latest \
    --region me-west1 \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars GCP_PROJECT_ID=gcp-rr-hub-core,GCP_REGION=me-west1,ADMIN_DOMAIN=liatsabag.altostrat.com \
    --project gcp-rr-hub-core

# Capture Deployed Backend URL
BACKEND_URL=$(gcloud run services describe gcp-rr-hub-backend --region=me-west1 --project=gcp-rr-hub-core --format='value(status.url)')

# 2. Deploy Frontend SPA
gcloud builds submit frontend --tag gcr.io/gcp-rr-hub-core/frontend:latest --project=gcp-rr-hub-core
gcloud run deploy gcp-rr-hub-frontend \
    --image gcr.io/gcp-rr-hub-core/frontend:latest \
    --region me-west1 \
    --platform managed \
    --allow-unauthenticated \
    --project gcp-rr-hub-core
```
**Verification Command:**
```bash
curl -s -f "${BACKEND_URL}/health" | jq .
```

---

### Step 9: Cloud Workflows Governance Cycle Deployment
Deploys the 2-step automated governance workflow (`fleet-governance-cycle`).

```bash
gcloud workflows deploy fleet-governance-cycle \
    --source=scripts/workflows/fleet_governance_cycle.yaml \
    --location=me-west1 \
    --project=gcp-rr-hub-core
```
**Verification Command:**
```bash
gcloud workflows run fleet-governance-cycle --location=me-west1 --project=gcp-rr-hub-core
```

---

## 4. Traffic Generation & Dynamic Cost Verification Manual

### 4.1 Understanding the Dynamic Cost Model
The platform does **not** operate on a fixed monthly subscription. All numbers reported in the FinOps dashboard and billing marts are **dynamic and usage-driven**, representing actual GCP consumption across 5 service lines:
* **BigQuery SQL**: Driven by `total_bytes_billed` scanned during analytical queries.
* **Vertex AI / Gemini**: Driven by `ai_token_count` consumed during prompts and DUA evaluations.
* **Colab Enterprise / Compute**: Driven by active `notebook_runtime_hours` on `e2-standard-4` VMs.
* **Cloud Storage**: Driven by `storage_bytes` stored in `inbound` and `export` buckets.
* **Cloud Run**: Driven by serverless container CPU/RAM execution time.

```
                    +-------------------------------------------------------------+
                    |                 TRAFFIC GENERATION FLOW                     |
                    +-------------------------------------------------------------+
                                                  │
                                                  ▼
                         +───────────────────────────────────────────────────+
                         | 1. Run Traffic Generators (Synthetic or Genuine)  |
                         |    • `generate_live_researcher_traffic.py`        |
                         |    • `generate_scaled_spoke_activity.py`          |
                         +────────────────────────┬──────────────────────────+
                                                  │
                                                  ▼
                         +───────────────────────────────────────────────────+
                         | 2. Sync GCS Footprint Capacity                    |
                         |    • `python3 scripts/etl/sync_storage_metrics.py` |
                         +────────────────────────┬──────────────────────────+
                                                  │
                                                  ▼
                         +───────────────────────────────────────────────────+
                         | 3. Trigger BigQuery Curation Procedures           |
                         |    • `CALL sp_sync_curated_audit_events();`       |
                         |    • `CALL sp_aggregate_daily_compute_metrics();` |
                         |    • `CALL sp_rollup_monthly_usage();`            |
                         +────────────────────────┬──────────────────────────+
                                                  │
                                                  ▼
                         +───────────────────────────────────────────────────+
                         | 4. Verify End-to-End Invariant & Attribution      |
                         |    • `python3 scripts/verification/verify_finops_e2e.py` |
                         +───────────────────────────────────────────────────+
```

### 4.2 Executing Workload Generators

#### Option A: Comprehensive Multi-Tenant Traffic Generator
Executes real BigQuery scans, Gemini API token calls, and GCS uploads labeled with genuine researcher emails:

```bash
# Run 5 query scans and 2,000 AI tokens per researcher across all rooms
python3 scripts/simulation/generate_live_researcher_traffic.py --scans 5 --tokens 2000
```

#### Option B: Scaled Activity Generator with Proportional Weighting
Generates scaled researcher queries and active Colab session logs weighted by principal investigator ratios:

```bash
python3 scripts/simulation/generate_scaled_spoke_activity.py --cycles 3
```

#### Option C: Interactive Genuine User Workload
Executes workloads strictly under the currently authenticated `gcloud` user account:

```bash
python3 scripts/simulation/interactive_researcher_executor.py --room rr-oncology-01
```

### 4.3 Post-Traffic Telemetry Synchronization

After running traffic generators, immediately sync storage metrics and execute the BigQuery curation procedures:

```bash
# 1. Sync live storage footprints (145.77 GB)
python3 scripts/etl/sync_storage_metrics.py

# 2. Trigger BigQuery Data Curation & Daily Aggregation
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_sync_curated_audit_events\`();"
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_sync_notebook_session_metrics\`();"
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_sync_ai_usage_metrics\`();"
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_aggregate_daily_compute_metrics\`();"
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_rollup_monthly_usage\`();"
```

### 4.4 Automated Sanity Check & Verification Suite

Execute the regression suites to verify BigQuery procedures, zero-drift balance math, bytes-billed SQL formulas, and API responses:

```bash
# 1. Run Telemetry & Stored Procedures Suite
python3 scripts/verification/verify_telemetry_finops.py

# 2. Run FinOps Attribution & Zero-Drift Balance Suite
python3 scripts/verification/verify_finops_e2e.py
```

#### Expected Test Output:
```
==================================================
   FINOPS END-TO-END CAPABILITY VERIFICATION      
==================================================
-> Total Invoiced Fleet Spend: $11.63
-> Direct Researcher Spend:    $6.84
-> Shared Overhead Spend:      $4.77
-> Central Hub Core Spend:     $0.02
...
   Room [rr-oncology-01] Total=$3.31 | Status=BALANCED (Variance=$0.0000)
   Room [rr-genomics-02] Total=$4.95 | Status=BALANCED (Variance=$0.0000)
   Room [rr-cardio-03]   Total=$2.12 | Status=BALANCED (Variance=$0.0000)
   Room [rr-neurology-04]Total=$1.23 | Status=BALANCED (Variance=$0.0000)
...
==================================================
   ALL FINOPS VERIFICATION CHECKS PASSED (100%)   
==================================================
```

---

## 5. Teardown & Resource Cleanup Guide

To prevent recurring GCP charges when pausing development or destroying test environments:

```bash
# 1. Delete Cloud Run Services
gcloud run services delete gcp-rr-hub-backend --region=me-west1 --project=gcp-rr-hub-core --quiet
gcloud run services delete gcp-rr-hub-frontend --region=me-west1 --project=gcp-rr-hub-core --quiet

# 2. Pause DTS Scheduled Queries
python3 -c "
from google.cloud import bigquery_datatransfer_v1
client = bigquery_datatransfer_v1.DataTransferServiceClient()
parent = 'projects/gcp-rr-hub-core/locations/me-west1'
for config in client.list_transfer_configs(parent=parent):
    client.update_transfer_config(transfer_config={'name': config.name, 'disabled': True}, update_mask={'paths': ['disabled']})
print('All DTS scheduled queries paused.')
"

# 3. Destroy Terraform Spoke Resources (Optional)
# cd terraform/environments/dev && terraform destroy -auto-approve
```
