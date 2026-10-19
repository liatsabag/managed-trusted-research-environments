-- scripts/sql/schema_telemetry.sql
-- Hub Telemetry, Regulatory Ledger, Airlock Requests, and Room Onboarding Requests

CREATE SCHEMA IF NOT EXISTS `hub_telemetry`
OPTIONS(
  location = 'me-west1',
  description = 'Operational telemetry, compliance ledgers, airlock queue, room requests, and audit marts'
);

-- 1. Regulatory Compliance Checklist Table (Unified Active Fleet & Prospective Requests Prerequisite Ledger)
CREATE OR REPLACE TABLE `hub_telemetry.ops_regulatory_checklist` (
    item_id STRING NOT NULL,
    room_id STRING NOT NULL,
    room_type STRING NOT NULL, -- 'PROVISIONED' or 'PENDING_REQUEST'
    item_type STRING NOT NULL,
    item_name STRING NOT NULL,
    status STRING NOT NULL,
    approval_date DATE,
    expiration_date DATE,
    approver_name STRING,
    document_uri STRING,
    comments STRING,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 2. Pre-Flight Room Onboarding Requests Table (Metadata, Proposal Details, & Governance Decision)
CREATE OR REPLACE TABLE `hub_telemetry.ops_room_requests` (
    request_id STRING NOT NULL,
    proposed_room_id STRING NOT NULL,
    room_name STRING NOT NULL,
    institute_id STRING NOT NULL,
    requested_by STRING NOT NULL,
    main_researcher STRING,
    purpose_of_research STRING,
    location STRING,
    expected_funds_usd NUMERIC,
    budget_limit_usd NUMERIC,
    expected_time_range STRING,
    document_folder_uri STRING NOT NULL,
    status STRING NOT NULL,
    gate_decision STRING,
    missing_items STRING,
    expired_items STRING,
    warning_items STRING,
    summary_reason STRING,
    scanned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 3. Air-Lock Egress Requests Table
CREATE OR REPLACE TABLE `hub_telemetry.ops_airlock_requests` (
    request_id STRING NOT NULL,
    room_id STRING NOT NULL,
    researcher_email STRING NOT NULL,
    file_name STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    status STRING NOT NULL,
    file_size_bytes INT64,
    row_count INT64,
    risk_score INT64,
    risk_level STRING,
    pii_detected BOOLEAN,
    small_cell_detected BOOLEAN,
    gemini_assessment STRING,
    dpo_reviewer_email STRING,
    review_comments STRING,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    reviewed_at TIMESTAMP,
    sla_deadline TIMESTAMP
);
