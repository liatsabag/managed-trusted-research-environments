# GCP Health Data Platform — Research Room Management System

[![Google Cloud Platform](https://img.shields.io/badge/GCP-Enterprise%20TRE-4285F4?logo=googlecloud&logoColor=white)](https://cloud.google.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![BigQuery](https://img.shields.io/badge/BigQuery-Analytics%20%26%20FinOps-669DF6?logo=googlebigquery&logoColor=white)](https://cloud.google.com/bigquery)
[![Vertex AI](https://img.shields.io/badge/Vertex%20AI-Gemini%203.7%20Flash-FF6F00?logo=google&logoColor=white)](https://cloud.google.com/vertex-ai)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

An enterprise-grade, zero-trust **Multi-Tenant Trusted Research Environment (TRE)** and centralized governance management platform on Google Cloud Platform. 

Designed for hospital networks, clinical research consortia, and life sciences organizations to deploy isolated research workspaces ("Research Rooms") with automated statutory ethics gating (Helsinki IRB, DUAs), dual-bucket Air-Lock egress protection, and FinOps cost accountability.

---

## 📖 Primary Documentation & Visual Runbooks

* 🏛️ **[System Architecture Specification (`ARCHITECTURE.md`)](file:///Users/liatsabag/research-room/ARCHITECTURE.md)**:
  - Complete project mission, isolation perimeters, and **VPC Service Controls (VPC-SC)** security model.
  - Comprehensive high-level and detailed multi-project visual topology.
  - Detailed visual sequence flows and cloud resource breakdowns for all 5 core backend processes (AI Compliance Scanning & IAM Soft-Downgrade, Real-Time Telemetry & Storage Ingestion, Two-Tiered FinOps Attribution, Air-Lock Egress DLP Review, and Governed Colab Execution).
  - Dynamic usage-based cost model explanation and Architectural Decision Records (ADRs).
* 🖥️ **[Visual Presentation Deck (`docs/gcp_tre_presentation.html`)](file:///Users/liatsabag/research-room/docs/gcp_tre_presentation.html)**:
  - Interactive 7-slide visual slide deck with modern light styling introducing the GCP TRE project vision, dual governance & FinOps control plane, entity model, AI compliance, and Air-Lock protection.
* 🎨 **[Technical Visual Diagrams (`docs/TECHNICAL_DIAGRAMS.md`)](file:///Users/liatsabag/research-room/docs/TECHNICAL_DIAGRAMS.md)**:
  - Multi-colored Mermaid sequence diagrams and high-contrast system architecture maps.
* 🚀 **[Zero-to-Production Deployment Runbook & Traffic Manual (`DEPLOYMENT.md`)](file:///Users/liatsabag/research-room/DEPLOYMENT.md)**:
  - Step-by-step copy-pasteable provisioning guide with immediate verification commands for every step.
  - **Traffic Generation & Workload Operations Manual**: Detailed CLI instructions to run synthetic and genuine multi-tenant researcher traffic across BigQuery, Vertex AI, GCS, and Colab Enterprise runtimes.
* 📊 **[FinOps Feature Summary (`FINOPS_FEATURE_SUMMARY.md`)](file:///Users/liatsabag/research-room/FINOPS_FEATURE_SUMMARY.md)**:
  - Detailed two-tiered proportional cost attribution engine rules, mathematical invariant proofs, and BigQuery billing export integration.
* 📋 **[Core Feature Summary (`FEATURE_SUMMARY.md`)](file:///Users/liatsabag/research-room/FEATURE_SUMMARY.md)**:
  - Summary of telemetry tables, stored procedures, scheduled queries, and REST APIs.

---

## 🌟 Key Capabilities

1. **Autonomous 2-Loop Governance & Soft-Downgrade**:
   - **Continuous Curation Loop**: BigQuery DTS schedules synchronize audit events, Colab notebook runtimes, and Vertex AI token logs every 15 minutes.
   - **AI Scanning & Soft-Downgrade Loop**: Google Cloud Workflows (`fleet-governance-cycle`) runs Vertex AI Gemini 3.7 Flash scans against unstructured PDF agreements. If approval expires, it automatically downgrades researcher IAM permissions to read-only viewer roles (`roles/bigquery.dataViewer`, `roles/storage.objectViewer`).
2. **Two-Tiered Proportional FinOps Attribution**:
   - Ingests ground-truth GCP Billing Export records into day-partitioned analytical marts.
   - Apportions BigQuery spend **strictly by `total_bytes_billed`**, Vertex AI by `ai_token_count`, Compute by `notebook_runtime_hours`, and Storage by `storage_bytes`.
   - Mathematically verified zero-drift balance invariant: $\text{Total Invoiced} \equiv \sum \text{Researcher Spend} + \text{Shared Overhead}$.
3. **Dual-Bucket Air-Lock Egress Protection**:
   - Dedicated `inbound` (read-only) and `export` (write-only quarantine) buckets per room.
   - Automated Gemini DLP risk scoring (small-cell count detection $k < 5$, direct PII/PHI flags, genomic re-identification analysis) with multi-stage DPO release workflows.
4. **Governed Private Colab Enterprise Workspaces**:
   - Dedicated spoke VPC subnets (`10.10.x.0/24`) with `disable_public_ip = true` and Cloud NAT.
   - Governed Jupyter notebooks with native `%%bqsql` magics and project-isolated service accounts.
5. **Role-Based Governance SPA**:
   - Three distinct persona dashboards: **Central Operations Admin**, **Technical Cloud Admin**, and **Data Privacy Officer (DPO)**.
   - Live telemetry visualizations, FinOps cost reconciliation, and real-time fleet health metrics.

---

## 📂 Repository Directory Layout

```
research-room/
├── ARCHITECTURE.md                 # In-Depth System Architecture & Sequence Flows
├── DEPLOYMENT.md                   # Zero-to-Production Deployment & Traffic Manual
├── FEATURE_SUMMARY.md              # Telemetry & Stored Procedure Specifications
├── FINOPS_FEATURE_SUMMARY.md       # FinOps Attribution Engine Specification
├── README.md                       # Repository Overview & Quickstart Guide
├── LICENSE                         # Apache 2.0 Open Source License
├── docker-compose.yml              # Local Development Multi-Container Setup
├── main.py                         # Root Application Entrypoint
├── backend/                        # FastAPI Backend Application (Python 3.10)
│   ├── app/
│   │   ├── api/v1/                 # REST Route Handlers (Rooms, FinOps, Telemetry, Airlock)
│   │   ├── core/                   # Configuration (Pydantic Settings) & In-Memory Cache
│   │   ├── models/                 # Strongly-Typed Pydantic Models & DTOs
│   │   └── services/               # Business Services (FinOps, Telemetry, Compliance, Fleet)
│   ├── Dockerfile                  # Production Cloud Run Container Build
│   └── requirements.txt            # Python Dependencies (FastAPI, Google Cloud SDKs)
├── docs/                           # Architectural Guidelines & Visual Presentations
│   ├── gcp_tre_presentation.html   # Interactive 7-Slide Visual Slide Deck
│   ├── TECHNICAL_DIAGRAMS.md       # Multi-Colored Mermaid Architecture Diagrams
│   └── architectural_standards.md  # Architectural Guidelines & GCP TRE Standards
├── frontend/                       # Central Administrator Portal SPA
│   ├── js/                         # Vanilla ES Modules, Chart.js & State Manager
│   ├── css/                        # Tailwind & Custom Styles
│   ├── index.html                  # Responsive Application Shell
│   ├── nginx.conf                  # Nginx Reverse Proxy with No-Cache Directives
│   └── Dockerfile                  # Lightweight Nginx Web Container Build
├── scripts/                        # Automated Provisioning, ETL, Simulation & Tooling
│   ├── README.md                   # Master Operations Runbook & CLI Guide
│   ├── dev_server.py               # Local Development Full-Stack Server
│   ├── fixtures/                   # Fleet Topology & Initial Seed Roster
│   ├── provisioning/               # GCP Infrastructure & Resource Provisioning
│   ├── simulation/                 # Multi-Tenant Traffic & Researcher Generators
│   ├── etl/                        # Data Curation, Storage Footprint & Billing Seeding
│   ├── verification/               # FinOps Invariant & Compliance Test Suites
│   ├── sql/                        # BigQuery DDL, Stored Procedures & Authorized Views
│   └── workflows/                  # Google Cloud Workflows Definitions
├── staging/                        # Staged Datasets & Governed Research Notebooks
│   ├── bigquery/                   # Staged JSON fixtures for BigQuery Datasets
│   ├── notebooks/                  # Governed Analytical Jupyter Notebooks
│   └── storage/                    # Staged Inbound & Export GCS File Trees
├── terraform/                      # Infrastructure-as-Code Modules
│   ├── environments/dev/           # Dev Environment Variable Definitions
│   ├── hub/                        # Central Hub BigQuery, IAM, and VPC-SC Modules
│   └── modules/room/               # Reusable Spoke Research Room Module
└── tests/                          # Automated Pytest Test Suite
    ├── unit/                       # Unit Tests (API, Compliance, FinOps, Fleet)
    └── e2e/                        # End-to-End Integration Tests
```

---

## ⚡ Traffic Generation & Verification Quickstart

```bash
# 1. Generate live multi-tenant traffic across all rooms
python3 scripts/simulation/generate_live_researcher_traffic.py --scans 5 --tokens 2000

# 2. Synchronize storage capacity footprints into BigQuery telemetry
python3 scripts/etl/sync_storage_metrics.py

# 3. Trigger BigQuery Data Curation & Daily Aggregation
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_sync_curated_audit_events\`();"
bq query --use_legacy_sql=false "CALL \`gcp-rr-hub-core.hub_telemetry.sp_aggregate_daily_compute_metrics\`();"

# 4. Run End-to-End FinOps Invariant Test Suite
python3 scripts/verification/verify_finops_e2e.py
```

---

## 📄 License
This project is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

