# GCP Health Data Platform — Technical Architecture & Visual Diagrams

This companion document provides detailed, high-contrast, multi-colored Mermaid diagrams illustrating the core technical workflows, networking boundaries, and automated pipelines of the **Google Cloud Multi-Tenant Trusted Research Environment (TRE)**.

---

## 1. Global Multi-Project System Topology & VPC-SC Security Perimeter

```mermaid
flowchart TD
    %% Global Styling
    classDef billingClass fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#78350f;
    classDef hubClass fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e3a8a;
    classDef vpcClass fill:#fee2e2,stroke:#ef4444,stroke-width:2px,stroke-dasharray: 5 5,color:#7f1d1d;
    classDef spokeClass fill:#f0fdf4,stroke:#22c55e,stroke-width:2px,color:#14532d;
    classDef aiClass fill:#faf5ff,stroke:#a855f7,stroke-width:2px,color:#581c87;
    classDef dbClass fill:#f8fafc,stroke:#64748b,stroke-width:1.5px,color:#0f172a;

    subgraph BillingSink["🏢 Google Cloud Billing Export Sink Project"]
        BillingTable[("📊 Partitioned GCP Billing Export Table<br/>• SKU IDs, List Prices, Negotiated Discounts<br/>• Invoiced Dollars Ground Truth")]:::billingClass
    end

    subgraph HubProject["🏢 Central Governance Hub Project (gcp-rr-hub-core)"]
        direction TB
        
        subgraph ServingPlane["Cloud Run Serving Plane (me-west1)"]
            FrontendSPA["🖥️ Central Admin Portal (Nginx SPA / Tailwind CSS)<br/>• Role Dashboards: Ops Admin, Cloud Engineer, DPO"]:::hubClass
            BackendAPI["⚙️ Governance REST API (FastAPI / Python 3.10)<br/>• Modules: /rooms, /finops, /telemetry, /airlock"]:::hubClass
        end

        subgraph AutomationPlane["Automated Governance & Telemetry Engines"]
            CloudWorkflow["⚡ Cloud Workflow: fleet-governance-cycle<br/>• Step 1: BigQuery AI Scan (sp_scan_governance)<br/>• Step 2: Cloud Run IAM Demotion (/compliance/enforce)"]:::hubClass
            DTS_Scheduler["⏰ BigQuery DTS Scheduled Queries (me-west1)<br/>• 15-min Operational Sync (sp_sync_curated_audit_events, sp_sync_bigquery_queries)<br/>• 24-hr Daily Storage & Rollup (sp_sync_storage_metrics, sp_aggregate_daily_compute_metrics, sp_rollup_monthly_usage)"]:::hubClass
            TelemetryPoller["🤖 Cloud Run Job: rr-telemetry-poller<br/>• Triggered every 15 min via Cloud Scheduler (rr-telemetry-poller-15m)<br/>• Polls Vertex AI Runtime API (locations/me-west1/notebookRuntimes)<br/>• Polls Cloud Monitoring API (GCE VM uptime & Vertex AI API calls)"]:::hubClass
        end

        subgraph HubDataLayer["BigQuery Central Data, AI & Registry Layer (me-west1)"]
            HubRegistry[("📁 Dataset: hub_registry<br/>• reg_institutes, reg_researchers, reg_research_rooms")]:::dbClass
            HubTelemetry[("📈 Dataset: hub_telemetry<br/>• ops_audit_events_curated, ops_notebook_sessions<br/>• ops_daily_compute_metrics, ops_monthly_usage_rollup")]:::dbClass
            BillingView[("👁️ Authorized View: view_billing_export")]:::billingClass
            GeminiRemote["🤖 BQ ML Remote Model: gemini_flash_model<br/>• Binds BigQuery SQL to Vertex AI Gemini 3.7 Flash"]:::aiClass
            ApprovalDocObj[("📑 Object Table: obj_approval_documents<br/>• Metadata index over unstructured PDF agreements")]:::dbClass
            SharedClinical[("🏥 Analytics Hub Data Exchanges<br/>• hub_shared_clinical & hub_shared_reference")]:::dbClass
        end

        HubApprovalsBucket[("🪣 Central Approvals GCS Bucket<br/>gs://gcp-rr-hub-approvals")]:::dbClass
        LogSinkRouter["📡 Central Cloud Logging Log Sink Router"]:::hubClass
    end

    subgraph VPCSC["🔒 VPC Service Controls Security Perimeter"]
        RestrictedAPIs["RESTRICTED SERVICES:<br/>• bigquery.googleapis.com<br/>• storage.googleapis.com<br/>• aiplatform.googleapis.com<br/>• logging.googleapis.com"]:::vpcClass
    end

    subgraph SpokeRooms["🔬 Tenant Spoke Research Rooms (gcp-rr-spoke-*)"]
        direction TB

        subgraph SpokeOncology["🔬 Spoke Room: rr-oncology-01"]
            VPC_Onco["Private VPC Subnet (10.10.1.0/24)<br/>• disable_public_ip = true | Cloud NAT"]:::spokeClass
            Colab_Onco["📓 Colab Enterprise (tpl-onco-default)<br/>• Shielded VM e2-standard-4"]:::spokeClass
            BQ_Onco[("Local Dataset & Linked Cohort")]:::dbClass
            GCS_In_1[("📥 Inbound Bucket (Read-Only)")]:::spokeClass
            GCS_Out_1[("📤 Export Bucket (Quarantine)")]:::spokeClass
        end

        subgraph SpokeGenomics["🧬 Spoke Room: rr-genomics-02"]
            VPC_Genom["Private VPC Subnet (10.10.2.0/24)<br/>• disable_public_ip = true | Cloud NAT"]:::spokeClass
            Colab_Genom["📓 Colab Enterprise (tpl-genom-default)<br/>• Shielded VM n2-highmem-8"]:::spokeClass
            BQ_Genom[("Local Dataset & Linked Panel")]:::dbClass
            GCS_In_2[("📥 Inbound Bucket (Read-Only)")]:::spokeClass
            GCS_Out_2[("📤 Export Bucket (Quarantine)")]:::spokeClass
        end
    end

    %% Flow Connections
    FrontendSPA --> BackendAPI
    BackendAPI --> HubDataLayer
    CloudWorkflow --> HubDataLayer & BackendAPI
    DTS_Scheduler --> HubTelemetry
    BillingTable --> BillingView --> HubTelemetry
    HubApprovalsBucket --> ApprovalDocObj --> GeminiRemote

    SharedClinical -.->|Linked Subscriptions| BQ_Onco & BQ_Genom
    HubProject <==> VPCSC <==> SpokeRooms
    SpokeRooms -->|Real-Time Audit Stream| LogSinkRouter --> HubTelemetry
```

---

## 2. Step-by-Step AI Compliance & IAM Soft-Downgrade Workflow

```mermaid
sequenceDiagram
    autonumber
    
    %% Participant Definitions with Color Annotations
    actor Operator as ⏱️ Cloud Scheduler / Operator
    participant WF as ⚡ Cloud Workflows (fleet-governance-cycle)
    participant BQ as 📊 BigQuery Engine (me-west1)
    participant GCS as 🪣 Approvals GCS Bucket
    participant Gemini as 🤖 Vertex AI Gemini 3.7 Flash
    participant Backend as ⚙️ FastAPI Backend (/compliance/enforce)
    participant IAM as 👥 Google Cloud IAM & Identity

    Operator->>WF: 1. Trigger Scheduled Governance Cycle
    activate WF
    
    rect rgb(239, 246, 255)
    Note over WF,Gemini: Step 1: BigQuery AI Compliance Scan
    WF->>BQ: CALL sp_scan_governance('PROVISIONED')
    activate BQ
    BQ->>GCS: Read PDF Documents via obj_approval_documents
    GCS-->>BQ: Raw PDF Binary Streams
    BQ->>Gemini: ML.GENERATE_TEXT(Prompt: Extract Expiry Date & IRB Clause)
    activate Gemini
    Gemini-->>BQ: Structured JSON: {expiry_date: "2026-10-15", status: "VALID"}
    deactivate Gemini
    BQ->>BQ: Update hub_telemetry.ops_regulatory_checklist
    BQ-->>WF: Scan Complete (Updated Statuses Recorded)
    deactivate BQ
    end

    rect rgb(254, 242, 242)
    Note over WF,IAM: Step 2: Enforce IAM Soft-Downgrade Policy
    WF->>Backend: HTTP POST (OIDC): /api/v1/compliance/enforce
    activate Backend
    Backend->>BQ: Query Expired Checklist Items from ops_regulatory_checklist
    BQ-->>Backend: Return Rooms where status = 'EXPIRED'
    
    loop For Each Non-Compliant Room
        Backend->>IAM: Demote Group Role: roles/bigquery.dataEditor -> roles/bigquery.dataViewer
        Backend->>IAM: Demote Storage Role: roles/storage.objectAdmin -> roles/storage.objectViewer
        Backend->>BQ: Update Room Status = SOFT_DOWNGRADED in reg_research_rooms
        Backend->>BQ: Record Action in ops_audit_events_curated
    end
    
    Backend-->>WF: Enforcement Results JSON (Rooms Downgraded: N)
    deactivate Backend
    end

    WF-->>Operator: Governance Cycle Completed Successfully
    deactivate WF
```

---

## 3. Step-by-Step Air-Lock Egress Review & Cryptographic Release Flow

```mermaid
sequenceDiagram
    autonumber

    actor Researcher as 👩‍⚕️ Researcher (Colab Enterprise)
    participant ExportBucket as 📤 Spoke Export Bucket (gs://rr-*-export/)
    participant AirlockAPI as ⚙️ FastAPI Airlock Service
    participant GeminiDLP as 🤖 Vertex AI Gemini DLP Evaluator
    participant BQ_Airlock as 📋 ops_airlock_requests (Marts)
    actor DPO as 🛡️ Data Privacy Officer (DPO Portal)
    participant DestBucket as 🌍 Approved External Destination

    Researcher->>ExportBucket: 1. Write Candidate Export File (e.g. summary_stats.csv)
    ExportBucket->>AirlockAPI: 2. File Upload Event Trigger / Candidate Registered
    activate AirlockAPI

    rect rgb(245, 243, 255)
    Note over AirlockAPI,GeminiDLP: Cryptographic Hashing & AI Privacy Evaluation
    AirlockAPI->>ExportBucket: Read File Content & Generate SHA-256 Checksum
    AirlockAPI->>GeminiDLP: Scan File for Small-Cell Counts (k < 5), PII/PHI & Patient Identifiers
    activate GeminiDLP
    GeminiDLP-->>AirlockAPI: Return AI Risk Card: {risk_score: 15, risk_level: "LOW", flags: []}
    deactivate GeminiDLP
    
    AirlockAPI->>BQ_Airlock: Insert Request Record (Status: PENDING_REVIEW, SHA-256, Risk Score)
    deactivate AirlockAPI
    end

    rect rgb(240, 253, 244)
    Note over DPO,DestBucket: Human-in-the-Loop DPO Review & Cryptographic Release
    DPO->>AirlockAPI: 3. GET /api/v1/airlock/requests (Inspect Pending Air-Lock Queue)
    AirlockAPI-->>DPO: Return File Metadata, Sample Data Preview & Gemini Risk Card
    
    DPO->>AirlockAPI: 4. POST /api/v1/airlock/requests/{id}/approve (Decision: APPROVED)
    activate AirlockAPI
    AirlockAPI->>ExportBucket: Copy File to Authorized External Destination
    ExportBucket->>DestBucket: Transfer Verified Egress Artifact
    AirlockAPI->>BQ_Airlock: Update Status = APPROVED, Record DPO Email & Timestamp
    AirlockAPI->>AirlockAPI: Insert Cryptographic Audit Record into ops_audit_events_curated
    AirlockAPI-->>DPO: 5. Release Confirmed (Signed Download URL Generated)
    deactivate AirlockAPI
    end
```

---

## 4. Two-Tiered FinOps Proportional Attribution Flow

```mermaid
flowchart TD
    classDef bill fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#78350f;
    classDef engine fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e3a8a;
    classDef level fill:#f0fdf4,stroke:#22c55e,stroke-width:2px,color:#14532d;
    classDef res fill:#faf5ff,stroke:#a855f7,stroke-width:2px,color:#581c87;
    classDef ovh fill:#f1f5f9,stroke:#64748b,stroke-width:2px,color:#334155;

    BillingExport["🏢 GCP Detailed Billing Export (Ground-Truth Invoiced Spend)"]:::bill
    
    subgraph GroundTelemetry["Ground-Truth Telemetry Engines"]
        direction TB
        BQ_IS["BigQuery INFORMATION_SCHEMA<br/>(Bytes Billed & Slot Hours via sp_sync_bigquery_queries)"]:::res
        GCS_SI["GCS Storage Insights & Object Creation Correlation<br/>(Physical Inventory via sp_sync_storage_metrics)"]:::res
        VAI_API["Vertex AI Runtimes API & Cloud Monitoring<br/>(VM Uptime & Runtime Hours via rr-telemetry-poller)"]:::res
        CM_API["Cloud Monitoring Metrics<br/>(Model Inferences & Tokens via rr-telemetry-poller)"]:::res
    end

    BQ_IS & GCS_SI & VAI_API & CM_API --> DailyMarts["📈 ops_daily_compute_metrics<br/>(Unified Ground-Truth Operational Mart)"]:::res
    BillingExport & DailyMarts --> FinOpsEngine["⚙️ FinOps Attribution Engine"]:::engine

    FinOpsEngine --> FleetLevel["1. Fleet Level Rollup (Total Invoiced, Runways, Forecasts)"]:::level
    FleetLevel --> RoomLevel["2. Research Room Level (Invoiced Spend per Room Project)"]:::level

    RoomLevel --> Split{"Proportional Attribution Split (W_r)"}

    Split -->|Direct Scanned Bytes Billed| ResBQ["BigQuery Spend &rarr; Researcher Weight (Bytes / &Sigma;Bytes)"]:::res
    Split -->|Direct Vertex AI Tokens| ResAI["Vertex AI Spend &rarr; Researcher Weight (Tokens / &Sigma;Tokens)"]:::res
    Split -->|Colab Runtime Hours| ResCompute["Compute Spend &rarr; Researcher Weight (Hours / &Sigma;Hours)"]:::res
    Split -->|GCS Storage Footprint| ResGCS["Storage Spend &rarr; Researcher Weight (GCS / &Sigma;GCS)"]:::res
    Split -->|System Jobs & Administrative Runners| Overhead["Shared Administrative Overhead (W_ovh = 1 - &Sigma; W_r)"]:::ovh

    ResBQ & ResAI & ResCompute & ResGCS --> ResearcherTotal["3. Individual Researcher Spend Summary"]:::res
    ResearcherTotal --> InstituteLevel["4. Sponsoring Institute Rollup (MSKCC, Broad, Hopkins)"]:::level

    Overhead -.->|Balanced Reconciliation| ZeroDrift["✅ Zero-Drift Balance: Total Invoiced &equiv; &Sigma; Researchers + Shared Overhead"]:::level
```

---

## 5. Entity Data Model & Relational Schema

```mermaid
erDiagram
    INSTITUTES ||--o{ RESEARCHERS : employs
    INSTITUTES ||--o{ RESEARCH_ROOMS : sponsors
    RESEARCHERS }o--o{ RESEARCH_ROOMS : assigned_to
    RESEARCH_ROOMS ||--o{ RESEARCH_STUDIES : hosts
    RESEARCH_ROOMS ||--o{ ROOM_PACKAGES : installs

    INSTITUTES {
        string institute_id PK "Unique Institute ID"
        string name "Broad, MSKCC, Johns Hopkins, Oxford"
        string country "Country of Registration"
        string contact_email "Institutional Contact"
    }

    RESEARCHERS {
        string researcher_id PK "Unique Researcher ID"
        string primary_email "Cloud Identity Email"
        string role "Principal Investigator, Fellow, Analyst"
        string access_state "ACTIVE, SOFT_DOWNGRADED"
        string cloud_identity_group "Assigned Identity Group"
    }

    RESEARCH_ROOMS {
        string room_id PK "Unique Room ID"
        string spoke_project_id "GCP Spoke Project ID"
        date helsinki_expiry_date "IRB Expiration Date"
        date dua_expiry_date "DUA Expiration Date"
        numeric budget_limit_usd "Assigned Budget Limit"
        string status "ACTIVE, SOFT_DOWNGRADED"
    }

    RESEARCH_STUDIES {
        string study_id PK "Study / Protocol ID"
        string lead_researcher_id FK "PI Researcher ID"
        string notebook_runtime_id "Colab Runtime Template"
        string status "IN_PROGRESS, COMPLETED"
    }

    ROOM_PACKAGES {
        string room_id FK "Spoke Room ID"
        string runtime_id "Colab Runtime Template"
        string package_name "Python / CRAN Package Name"
        string package_version "Pinned Package Version"
    }
```
