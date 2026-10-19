-- scripts/sql/curate_audit_events.sql
-- Curated Audit Mart DDL, Transformation ELT, and Dynamic Stored Procedure

-- 1. Create Curated Audit Mart Table (Partitioned by Day, Clustered by room_id, category, principal_email)
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_audit_events_curated` (
    log_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    room_id STRING NOT NULL,
    project_id STRING NOT NULL,
    principal_email STRING NOT NULL,
    category STRING NOT NULL, -- DATA_ACCESS, COMPUTE_SESSION, STORAGE_EGRESS, IAM_SECURITY, AI_INFERENCE
    service_name STRING NOT NULL,
    action_name STRING NOT NULL,
    resource_name STRING,
    status STRING NOT NULL,
    severity STRING NOT NULL,
    description STRING NOT NULL,
    metadata_json STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY room_id, category, principal_email
OPTIONS(
    description = 'Curated operational audit events dynamically resolved across active research rooms'
);

-- 2. Stored Procedure for Dynamic Incremental ELT from Raw Cloud Audit Tables
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_sync_curated_audit_events`()
BEGIN
    MERGE `hub_telemetry.ops_audit_events_curated` T
    USING (
        WITH raw_events AS (
            SELECT
                COALESCE(raw.insertId, GENERATE_UUID()) AS log_id,
                raw.timestamp AS timestamp,
                COALESCE(
                    r.room_id,
                    IF(raw.raw_project_id = 'gcp-rr-hub-core' OR raw.raw_project_id IS NULL, 'hub-core', raw.raw_project_id)
                ) AS room_id,
                COALESCE(raw.raw_project_id, 'gcp-rr-hub-core') AS project_id,
                COALESCE(raw.principal_email, 'system@google.com') AS principal_email,
                CASE
                    -- Colab Enterprise / Compute Sessions
                    WHEN LOWER(raw.service_name) LIKE '%aiplatform%' AND (
                         LOWER(raw.method_name) LIKE '%notebook%' 
                         OR LOWER(raw.method_name) LIKE '%runtime%'
                         OR LOWER(COALESCE(raw.resource_name, '')) LIKE '%notebookruntime%'
                    ) THEN 'COMPUTE_SESSION'
                    WHEN LOWER(raw.service_name) LIKE '%notebooks%'
                         OR LOWER(raw.service_name) LIKE '%compute%'
                         OR LOWER(raw.method_name) LIKE '%instance%'
                         OR LOWER(raw.method_name) LIKE '%session%' THEN 'COMPUTE_SESSION'
                    -- Vertex AI / Gemini Inference
                    WHEN LOWER(raw.service_name) LIKE '%aiplatform%'
                         OR LOWER(raw.method_name) LIKE '%predict%'
                         OR LOWER(raw.method_name) LIKE '%generatecontent%'
                         OR LOWER(raw.method_name) LIKE '%counttokens%' THEN 'AI_INFERENCE'
                    -- IAM & Governance Security
                    WHEN LOWER(raw.service_name) LIKE '%iam%'
                         OR LOWER(raw.service_name) LIKE '%resourcemanager%'
                         OR LOWER(raw.method_name) LIKE '%iampolicy%'
                         OR LOWER(raw.method_name) LIKE '%key%' THEN 'IAM_SECURITY'
                    -- Storage & Egress
                    WHEN LOWER(raw.service_name) LIKE '%storage%'
                         AND (LOWER(COALESCE(raw.resource_name, '')) LIKE '%export%'
                              OR LOWER(raw.method_name) LIKE '%export%'
                              OR LOWER(raw.method_name) LIKE '%copy%') THEN 'STORAGE_EGRESS'
                    -- Data Access
                    WHEN LOWER(raw.service_name) LIKE '%bigquery%'
                         OR LOWER(raw.service_name) LIKE '%storage%' THEN 'DATA_ACCESS'
                    ELSE 'DATA_ACCESS'
                END AS category,
                COALESCE(raw.service_name, 'unknown.googleapis.com') AS service_name,
                COALESCE(raw.method_name, 'UnknownAction') AS action_name,
                raw.resource_name AS resource_name,
                CASE
                    WHEN raw.status_code IS NULL OR raw.status_code = 0 THEN 'SUCCESS'
                    ELSE COALESCE(raw.status_message, 'ERROR')
                END AS status,
                COALESCE(raw.severity, 'INFO') AS severity,
                CASE
                    WHEN LOWER(raw.service_name) LIKE '%bigquery%' AND LOWER(raw.method_name) LIKE '%job%'
                        THEN CONCAT('BigQuery job executed by ', COALESCE(raw.principal_email, 'user'), ' on ', COALESCE(raw.resource_name, 'BigQuery resource'))
                    WHEN LOWER(raw.service_name) LIKE '%storage%' AND (LOWER(COALESCE(raw.resource_name, '')) LIKE '%export%' OR LOWER(raw.method_name) LIKE '%copy%')
                        THEN CONCAT('Egress storage transfer initiated by ', COALESCE(raw.principal_email, 'user'), ' to ', COALESCE(raw.resource_name, 'export bucket'))
                    WHEN LOWER(raw.service_name) LIKE '%storage%'
                        THEN CONCAT('Cloud Storage access by ', COALESCE(raw.principal_email, 'user'), ' on ', COALESCE(raw.resource_name, 'storage object'))
                    WHEN LOWER(raw.service_name) LIKE '%aiplatform%' AND (LOWER(raw.method_name) LIKE '%notebook%' OR LOWER(raw.method_name) LIKE '%runtime%')
                        THEN CONCAT('Colab Enterprise notebook runtime operation (', raw.method_name, ') by ', COALESCE(raw.principal_email, 'user'))
                    WHEN LOWER(raw.service_name) LIKE '%notebooks%' OR LOWER(raw.method_name) LIKE '%instance%'
                        THEN CONCAT('Compute session operation (', raw.method_name, ') by ', COALESCE(raw.principal_email, 'user'))
                    WHEN LOWER(raw.service_name) LIKE '%aiplatform%' OR LOWER(raw.method_name) LIKE '%generatecontent%'
                        THEN CONCAT('AI inference invocation by ', COALESCE(raw.principal_email, 'user'))
                    WHEN LOWER(raw.service_name) LIKE '%iam%' OR LOWER(raw.method_name) LIKE '%iampolicy%'
                        THEN CONCAT('IAM authorization change by ', COALESCE(raw.principal_email, 'user'), ' on ', COALESCE(raw.resource_name, 'resource'))
                    ELSE CONCAT(COALESCE(raw.method_name, 'Action'), ' performed on ', COALESCE(raw.resource_name, 'resource'), ' by ', COALESCE(raw.principal_email, 'user'))
                END AS description,
                raw.metadata_json AS metadata_json
            FROM (
                SELECT
                    insertId,
                    timestamp,
                    logName,
                    COALESCE(resource.labels.project_id, REGEXP_EXTRACT(logName, r'projects/([^/]+)')) AS raw_project_id,
                    protopayload_auditlog.serviceName AS service_name,
                    protopayload_auditlog.methodName AS method_name,
                    protopayload_auditlog.resourceName AS resource_name,
                    protopayload_auditlog.authenticationInfo.principalEmail AS principal_email,
                    protopayload_auditlog.status.code AS status_code,
                    protopayload_auditlog.status.message AS status_message,
                    severity,
                    protopayload_auditlog.metadataJson AS metadata_json
                FROM `hub_telemetry.cloudaudit_googleapis_com_activity`
                WHERE protopayload_auditlog.serviceName IS NOT NULL
                UNION ALL
                SELECT
                    insertId,
                    timestamp,
                    logName,
                    COALESCE(resource.labels.project_id, REGEXP_EXTRACT(logName, r'projects/([^/]+)')) AS raw_project_id,
                    protopayload_auditlog.serviceName AS service_name,
                    protopayload_auditlog.methodName AS method_name,
                    protopayload_auditlog.resourceName AS resource_name,
                    protopayload_auditlog.authenticationInfo.principalEmail AS principal_email,
                    protopayload_auditlog.status.code AS status_code,
                    protopayload_auditlog.status.message AS status_message,
                    severity,
                    protopayload_auditlog.metadataJson AS metadata_json
                FROM `hub_telemetry.cloudaudit_googleapis_com_data_access`
                WHERE protopayload_auditlog.serviceName IS NOT NULL
                UNION ALL
                SELECT
                    insertId,
                    timestamp,
                    logName,
                    COALESCE(resource.labels.project_id, REGEXP_EXTRACT(logName, r'projects/([^/]+)')) AS raw_project_id,
                    protopayload_auditlog.serviceName AS service_name,
                    protopayload_auditlog.methodName AS method_name,
                    protopayload_auditlog.resourceName AS resource_name,
                    protopayload_auditlog.authenticationInfo.principalEmail AS principal_email,
                    protopayload_auditlog.status.code AS status_code,
                    protopayload_auditlog.status.message AS status_message,
                    severity,
                    CAST(NULL AS STRING) AS metadata_json
                FROM `hub_telemetry.cloudaudit_googleapis_com_system_event`
                WHERE protopayload_auditlog.serviceName IS NOT NULL
            ) raw
            LEFT JOIN `hub_registry.reg_research_rooms` r
                ON r.spoke_project_id = raw.raw_project_id
        )
        SELECT * FROM raw_events
    ) S
    ON T.log_id = S.log_id AND T.timestamp = S.timestamp
    WHEN NOT MATCHED THEN
        INSERT (log_id, timestamp, room_id, project_id, principal_email, category, service_name, action_name, resource_name, status, severity, description, metadata_json)
        VALUES (S.log_id, S.timestamp, S.room_id, S.project_id, S.principal_email, S.category, S.service_name, S.action_name, S.resource_name, S.status, S.severity, S.description, S.metadata_json);
END;
