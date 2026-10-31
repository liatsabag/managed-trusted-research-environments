# Managed Trusted Research Environments (TRE) on GCP

A zero-trust, multi-tenant governance and observability platform on Google Cloud Platform for managing secure research environments.

---

## 1. Project Goal & Overview

The goal of this platform is to provide a centralized administrative control plane to deploy, govern, monitor, and financially manage isolated research environments ("Research Rooms") on Google Cloud.

There is high demand for such solutions across public sector entities and regulated environments, including health authorities, government ministries, higher education and research consortia, and financial institutions.

### Core Architectural Synthesis
The platform brings together four key elements into a unified system:

* **Google Cloud Secure Research Blueprints**: Built on GCP native building blocks for secure data collaboration, including BigQuery data clean rooms, Analytics Hub zero-copy data exchanges, VPC Service Controls (VPC-SC) perimeters, and standardized Colab Enterprise notebook runtimes.
* **Hub-and-Spoke Unified Governance**: Solves the problem of siloed, fragmented research projects by establishing a central management hub (`gcp-rr-hub-core`) that orchestrates decentralized tenant workspaces (`gcp-rr-spoke-*`), providing unified identity, central audit logging, and consolidated FinOps across all environments.
* **AI-Powered Operational Automations**: Leverages Google Vertex AI (Gemini 3.7 Flash) to automate high-friction internal procedures, such as continuous statutory compliance scanning over regulatory approval documents (triggering automated IAM soft-downgrades if approvals lapse) and tabular privacy risk analysis (PII and small-cell disclosure detection) on egress files.
* **Lightweight Administrative UI**: A responsive, single-page management portal providing role-specific dashboards for Operations Administrators, Cloud Engineers, and Data Protection Officers.

---

## 2. High-Level Architecture

The platform follows a centralized Hub-and-Spoke architecture enclosed within a VPC Service Controls security perimeter:

![GCP Multi-Tenant TRE Target Architecture](docs/assets/gcp_tre_architecture.png)

*Detailed GCP TRE Architecture Blueprint (`gcp_tre_architecture.png`).*

---

## 3. Key Solution Values

* **Unified Multi-Tenant Governance**: Eliminates administrative silos by managing all tenant workspaces, permissions, and audit logs from a single control plane.
* **Zero Egress Risk**: Datasets remain enclosed within private VPC Service Controls perimeters. Egress is restricted to an Air-Lock quarantine bucket requiring AI privacy risk scoring and Data Protection Officer sign-off.
* **Autonomous Statutory Compliance**: Continuous AI verification of regulatory checklists automatically demotes expired rooms from active write/execute roles to read-only viewer roles, maintaining analytical continuity without regulatory non-compliance.
* **Two-Tiered FinOps Cost Attribution**: Reconciles ground-truth cloud spend from Google Cloud Billing exports against granular telemetry weights (BigQuery bytes billed, Colab runtime hours, Vertex AI token consumption, and storage bytes) to attribute costs down to individual researchers and shared administrative overhead.
* **Zero-Copy Data Collaboration**: Utilizes BigQuery Analytics Hub to share curated datasets across independent spoke projects without physical data duplication.

---

## 4. Repository Structure

```text
managed-trusted-research-environments/
├── ARCHITECTURE.md                         # Consolidated master technical architecture & deep dive
├── DEPLOYMENT.md                           # Step-by-step provisioning guide & operational scripts catalog
├── LICENSE                                 # Apache 2.0 open-source license
├── README.md                               # Project overview, architecture & value proposition
├── backend/                                # FastAPI REST application
│   ├── app/
│   │   ├── api/                            # API routes (/rooms, /finops, /telemetry, /compliance, /airlock)
│   │   ├── models/                         # Pydantic schemas and data models
│   │   └── services/                       # Business logic, BigQuery connectors, and AI risk scanners
│   └── tests/                              # Backend unit and integration test suite
├── frontend/                               # Single-Page Application (HTML5, Tailwind CSS, Chart.js)
│   ├── index.html                          # Main dashboard interface
│   ├── js/                                 # View modules, API clients, and telemetry charts
│   └── css/                                # Styling configurations
├── scripts/                                # Operational automation and provisioning scripts
│   ├── provisioning/                       # Infrastructure and service provisioning scripts
│   ├── etl/                                # Telemetry sync, metrics aggregation, and billing seeders
│   ├── simulation/                         # Multi-tenant workload and traffic simulation scripts
│   ├── verification/                       # Infrastructure audits and FinOps invariant tests
│   ├── sql/                                # BigQuery DDL, views, and analytical stored procedures
│   └── dev_server.py                       # Unified local development server runner
└── tests/                                  # End-to-end and unit test suites
```

---

## 5. Quickstart & Local Development

### Prerequisites
* Python 3.10+
* Google Cloud SDK (`gcloud` CLI) authenticated
* Standard Python dependencies installed:

```bash
git clone https://github.com/<your-org-or-username>/managed-trusted-research-environments.git
cd managed-trusted-research-environments
pip install -r requirements.txt
```

### Running the Local Development Server
To launch both the FastAPI backend and frontend user interface locally:

```bash
python scripts/dev_server.py
```

* **Frontend Management Portal**: Open your browser at `http://localhost:8000`
* **Interactive API Documentation**: Explore the REST API at `http://localhost:8000/docs`

---

## 6. Documentation Index

* **[Comprehensive Architecture Specification (ARCHITECTURE.md)](./ARCHITECTURE.md)**: Deep dive into the Hub-and-Spoke design, building blocks, VPC Service Controls perimeters, operational sequence workflows, and two-tiered FinOps attribution model.
* **[Deployment Guide & Operational Runbook (DEPLOYMENT.md)](./DEPLOYMENT.md)**: Zero-to-cloud provisioning steps, master script catalog, and traffic simulation instructions.
* **[Interactive Presentation Deck (docs/gcp_tre_presentation.html)](./docs/gcp_tre_presentation.html)**: Standalone visual slide presentation illustrating the platform architecture and operational flows.
