-- scripts/sql/finops_usage_tracking.sql
-- Colab Enterprise Notebook Sessionization & AI Telemetry Physical Marts and Stored Procedures
-- Uses idempotent MERGE to guarantee historical continuity without TRUNCATE

-- 1. Table: ops_notebook_sessions (Colab Enterprise & BigQuery Studio Notebook Tracking)
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_notebook_sessions` (
    room_id STRING NOT NULL,
    user_email STRING NOT NULL,
    session_date DATE NOT NULL,
    notebook_name STRING,
    runtime_id STRING,
    machine_type STRING,
    runtime_template_id STRING,
    total_events INT64,
    session_starts INT64,
    session_stops INT64,
    total_sessions INT64,
    total_active_hours NUMERIC,
    first_session_start TIMESTAMP,
    last_session_end TIMESTAMP
)
PARTITION BY session_date
CLUSTER BY room_id, user_email, runtime_template_id
OPTIONS(
    description = 'Persisted daily Colab Enterprise and BigQuery Studio notebook runtime sessions per researcher and machine type'
);

-- 2. Procedure: sp_sync_notebook_session_metrics (Idempotent MERGE without TRUNCATE)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_sync_notebook_session_metrics`()
BEGIN
    MERGE `hub_telemetry.ops_notebook_sessions` T
    USING (
        WITH session_events AS (
            SELECT
                room_id,
                principal_email AS user_email,
                DATE(timestamp) AS session_date,
                log_id,
                timestamp,
                service_name,
                action_name,
                resource_name,
                category,
                status,
                metadata_json,
                -- Extract Colab Enterprise runtime template if present in metadata or resource
                COALESCE(
                    JSON_VALUE(metadata_json, '$.notebookRuntimeTemplate'),
                    JSON_VALUE(metadata_json, '$.runtimeTemplate'),
                    CASE
                        WHEN LOWER(resource_name) LIKE '%genomics%' THEN 'tpl-highmem-genomics'
                        WHEN LOWER(resource_name) LIKE '%gpu%' OR LOWER(resource_name) LIKE '%deeplearning%' THEN 'tpl-gpu-deeplearning'
                        WHEN LOWER(resource_name) LIKE '%epidemiology%' OR LOWER(resource_name) LIKE '%-r-%' THEN 'tpl-r-epidemiology'
                        ELSE 'tpl-standard-ml'
                    END
                ) AS runtime_template_id,
                -- Extract machine type (e.g. e2-standard-4, n2-highmem-8, g2-standard-8)
                COALESCE(
                    JSON_VALUE(metadata_json, '$.machineType'),
                    JSON_VALUE(metadata_json, '$.machineSpec.machineType'),
                    CASE
                        WHEN LOWER(resource_name) LIKE '%genomics%' THEN 'n2-highmem-8'
                        WHEN LOWER(resource_name) LIKE '%gpu%' OR LOWER(resource_name) LIKE '%deeplearning%' THEN 'g2-standard-8'
                        WHEN LOWER(resource_name) LIKE '%epidemiology%' OR LOWER(resource_name) LIKE '%-r-%' THEN 'e2-standard-2'
                        ELSE 'e2-standard-4'
                    END
                ) AS machine_type,
                -- Extract Notebook name
                COALESCE(
                    JSON_VALUE(metadata_json, '$.notebookName'),
                    REGEXP_EXTRACT(resource_name, r'/([^/]+\.ipynb)'),
                    REGEXP_EXTRACT(resource_name, r'notebookRuntimes/([^/]+)'),
                    'cohort_analysis.ipynb'
                ) AS notebook_name,
                -- Extract Colab Enterprise runtime ID
                COALESCE(
                    JSON_VALUE(metadata_json, '$.runtimeId'),
                    REGEXP_EXTRACT(resource_name, r'notebookRuntimes/([^/]+)'),
                    'colab-runtime-default'
                ) AS runtime_id
            FROM `hub_telemetry.ops_audit_events_curated`
            WHERE (
                category = 'COMPUTE_SESSION'
                OR LOWER(service_name) LIKE '%aiplatform%'
                OR LOWER(service_name) LIKE '%notebooks%'
                OR LOWER(action_name) LIKE '%notebookruntime%'
            )
            AND principal_email IS NOT NULL
            AND principal_email != ''
        ),
        session_aggregates AS (
            SELECT
                room_id,
                user_email,
                session_date,
                ANY_VALUE(notebook_name) AS notebook_name,
                runtime_id,
                ANY_VALUE(machine_type) AS machine_type,
                ANY_VALUE(runtime_template_id) AS runtime_template_id,
                COUNT(DISTINCT log_id) AS total_events,
                COUNT(DISTINCT IF(
                    LOWER(action_name) LIKE '%assign%' 
                    OR LOWER(action_name) LIKE '%start%' 
                    OR LOWER(action_name) LIKE '%create%', 
                    log_id, NULL
                )) AS session_starts,
                COUNT(DISTINCT IF(
                    LOWER(action_name) LIKE '%stop%' 
                    OR LOWER(action_name) LIKE '%delete%'
                    OR LOWER(action_name) LIKE '%terminate%', 
                    log_id, NULL
                )) AS session_stops,
                MIN(timestamp) AS first_session_start,
                MAX(timestamp) AS last_session_end,
                -- Distinct active hourly blocks capped by realistic daily work limits
                LEAST(GREATEST(COUNT(DISTINCT FORMAT_TIMESTAMP('%H', timestamp)), 1), 4) AS total_sessions,
                -- Realistic active session duration capped by idle timeout threshold and working day bounds
                CAST(ROUND(
                    CASE
                        -- When there is an activity time span within the day:
                        WHEN TIMESTAMP_DIFF(MAX(timestamp), MIN(timestamp), MINUTE) > 0
                        THEN LEAST(
                            GREATEST(TIMESTAMP_DIFF(MAX(timestamp), MIN(timestamp), MINUTE) / 60.0 + 0.5, 1.0),
                            8.0
                        )
                        -- Single event or burst: 1.0 hour
                        ELSE 1.0
                    END,
                    2
                ) AS NUMERIC) AS estimated_active_hours
            FROM session_events
            GROUP BY room_id, user_email, session_date, runtime_id
        )
        SELECT
            room_id,
            user_email,
            session_date,
            notebook_name,
            runtime_id,
            machine_type,
            runtime_template_id,
            total_events,
            session_starts,
            session_stops,
            total_sessions,
            estimated_active_hours AS total_active_hours,
            first_session_start,
            last_session_end
        FROM session_aggregates
    ) S
    ON T.session_date = S.session_date 
       AND T.room_id = S.room_id 
       AND T.user_email = S.user_email 
       AND T.runtime_id = S.runtime_id
    WHEN MATCHED THEN
        UPDATE SET
            notebook_name = S.notebook_name,
            machine_type = S.machine_type,
            runtime_template_id = S.runtime_template_id,
            total_events = S.total_events,
            session_starts = S.session_starts,
            session_stops = S.session_stops,
            total_sessions = S.total_sessions,
            total_active_hours = S.total_active_hours,
            first_session_start = S.first_session_start,
            last_session_end = S.last_session_end
    WHEN NOT MATCHED THEN
        INSERT (room_id, user_email, session_date, notebook_name, runtime_id, machine_type, runtime_template_id, total_events, session_starts, session_stops, total_sessions, total_active_hours, first_session_start, last_session_end)
        VALUES (S.room_id, S.user_email, S.session_date, S.notebook_name, S.runtime_id, S.machine_type, S.runtime_template_id, S.total_events, S.session_starts, S.session_stops, S.total_sessions, S.total_active_hours, S.first_session_start, S.last_session_end);
END;

-- 3. Table: ops_ai_usage_metrics (Daily AI and Gemini Inference Metrics per Researcher)
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_ai_usage_metrics` (
    room_id STRING NOT NULL,
    project_id STRING NOT NULL,
    user_email STRING NOT NULL,
    usage_date DATE NOT NULL,
    service_name STRING NOT NULL,
    total_inference_calls INT64,
    ai_token_count INT64,
    successful_calls INT64,
    failed_calls INT64,
    first_invoked_at TIMESTAMP,
    last_invoked_at TIMESTAMP
)
PARTITION BY usage_date
CLUSTER BY room_id, user_email
OPTIONS(
    description = 'Persisted daily AI and Gemini inference invocation counts and tokens per researcher'
);

-- 4. Procedure: sp_sync_ai_usage_metrics (Idempotent MERGE without TRUNCATE)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_sync_ai_usage_metrics`()
BEGIN
    MERGE `hub_telemetry.ops_ai_usage_metrics` T
    USING (
        WITH ai_events AS (
            SELECT
                room_id,
                project_id,
                principal_email AS user_email,
                DATE(timestamp) AS usage_date,
                log_id,
                timestamp,
                service_name,
                action_name,
                resource_name,
                status,
                severity,
                metadata_json
            FROM `hub_telemetry.ops_audit_events_curated`
            WHERE category = 'AI_INFERENCE'
               OR LOWER(service_name) LIKE '%aiplatform%'
               OR LOWER(action_name) LIKE '%predict%'
               OR LOWER(action_name) LIKE '%generatecontent%'
               OR LOWER(action_name) LIKE '%counttokens%'
        )
        SELECT
            room_id,
            project_id,
            user_email,
            usage_date,
            service_name,
            COUNT(1) AS total_inference_calls,
            -- If real token count is logged in metadata, extract it; else derive default token count
            SUM(COALESCE(
                SAFE_CAST(JSON_VALUE(metadata_json, '$.usageMetadata.totalTokenCount') AS INT64),
                SAFE_CAST(JSON_VALUE(metadata_json, '$.tokenCount') AS INT64),
                1500
            )) AS ai_token_count,
            COUNTIF(status = 'SUCCESS') AS successful_calls,
            COUNTIF(status != 'SUCCESS') AS failed_calls,
            MIN(timestamp) AS first_invoked_at,
            MAX(timestamp) AS last_invoked_at
        FROM ai_events
        GROUP BY room_id, project_id, user_email, usage_date, service_name
    ) S
    ON T.usage_date = S.usage_date 
       AND T.room_id = S.room_id 
       AND T.user_email = S.user_email 
       AND T.service_name = S.service_name
    WHEN MATCHED THEN
        UPDATE SET
            total_inference_calls = S.total_inference_calls,
            ai_token_count = S.ai_token_count,
            successful_calls = S.successful_calls,
            failed_calls = S.failed_calls,
            first_invoked_at = S.first_invoked_at,
            last_invoked_at = S.last_invoked_at
    WHEN NOT MATCHED THEN
        INSERT (room_id, project_id, user_email, usage_date, service_name, total_inference_calls, ai_token_count, successful_calls, failed_calls, first_invoked_at, last_invoked_at)
        VALUES (S.room_id, S.project_id, S.user_email, S.usage_date, S.service_name, S.total_inference_calls, S.ai_token_count, S.successful_calls, S.failed_calls, S.first_invoked_at, S.last_invoked_at);
END;
