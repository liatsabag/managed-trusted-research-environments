-- scripts/sql/aggregate_compute_metrics.sql
-- Daily & Monthly Compute Aggregations DDL & Dynamic Stored Procedures

-- 1. Table: ops_daily_compute_metrics
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_daily_compute_metrics` (
    usage_date DATE NOT NULL,
    room_id STRING NOT NULL,
    user_email STRING NOT NULL,
    institute_id STRING,
    query_count INT64,
    total_bytes_billed INT64,
    total_slot_hours NUMERIC,
    notebook_runtime_hours NUMERIC,
    ai_inference_count INT64,
    ai_token_count INT64,
    storage_bytes INT64
)
PARTITION BY usage_date
CLUSTER BY room_id, user_email
OPTIONS(
    description = 'Unified daily compute, AI inference, and storage usage metrics per researcher'
);

-- 2. Stored Procedure: sp_aggregate_daily_compute_metrics (Dynamic across active spoke projects & curated audit trail)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_aggregate_daily_compute_metrics`()
BEGIN
    TRUNCATE TABLE `hub_telemetry.ops_daily_compute_metrics`;
    INSERT INTO `hub_telemetry.ops_daily_compute_metrics` (
        usage_date, room_id, user_email, institute_id, query_count,
        total_bytes_billed, total_slot_hours, notebook_runtime_hours,
        ai_inference_count, ai_token_count, storage_bytes
    )
    WITH bq_jobs AS (
        SELECT
            room_id,
            principal_email AS user_email,
            DATE(timestamp) AS usage_date,
            COUNT(1) AS query_count,
            SUM(
                COALESCE(
                    SAFE_CAST(JSON_VALUE(metadata_json, '$.jobChange.after.jobStats.queryStats.totalBilledBytes') AS INT64),
                    SAFE_CAST(JSON_VALUE(metadata_json, '$.jobCompletedEvent.job.jobStatistics.totalBilledBytes') AS INT64),
                    52428800 -- 50MB default fallback if JSON metadata is not populated
                )
            ) AS total_bytes_billed,
            CAST(ROUND(
                SUM(
                    COALESCE(
                        SAFE_CAST(JSON_VALUE(metadata_json, '$.jobChange.after.jobStats.queryStats.totalSlotMs') AS FLOAT64) / 3600000.0,
                        SAFE_CAST(JSON_VALUE(metadata_json, '$.jobCompletedEvent.job.jobStatistics.totalSlotMs') AS FLOAT64) / 3600000.0,
                        0.0001
                    )
                ), 5) AS NUMERIC) AS total_slot_hours
        FROM `hub_telemetry.ops_audit_events_curated`
        WHERE service_name = 'bigquery.googleapis.com'
          AND category = 'DATA_ACCESS'
          AND room_id IS NOT NULL
          AND room_id != 'hub-core'
        GROUP BY 1, 2, 3
    ),
    notebook_hours AS (
        SELECT
            room_id,
            user_email,
            session_date AS usage_date,
            CAST(ROUND(SUM(total_active_hours), 2) AS NUMERIC) AS notebook_runtime_hours
        FROM `hub_telemetry.ops_notebook_sessions`
        GROUP BY 1, 2, 3
    ),
    ai_usage AS (
        SELECT
            room_id,
            user_email,
            usage_date,
            SUM(COALESCE(total_inference_calls, 0)) AS ai_inference_count,
            SUM(COALESCE(total_inference_calls, 0) * 1500) AS ai_token_count
        FROM `hub_telemetry.ops_ai_usage_metrics`
        GROUP BY 1, 2, 3
    ),
    all_keys AS (
        SELECT room_id, user_email, usage_date FROM bq_jobs WHERE room_id IS NOT NULL
        UNION DISTINCT
        SELECT room_id, user_email, usage_date FROM notebook_hours WHERE room_id IS NOT NULL
        UNION DISTINCT
        SELECT room_id, user_email, usage_date FROM ai_usage WHERE room_id IS NOT NULL
    ),
    combined AS (
        SELECT
            k.usage_date,
            k.room_id,
            k.user_email,
            COALESCE(r.institute_id, 'inst-unknown') AS institute_id,
            COALESCE(q.query_count, 0) AS query_count,
            COALESCE(q.total_bytes_billed, 0) AS total_bytes_billed,
            COALESCE(q.total_slot_hours, 0) AS total_slot_hours,
            COALESCE(n.notebook_runtime_hours, 0) AS notebook_runtime_hours,
            COALESCE(a.ai_inference_count, 0) AS ai_inference_count,
            COALESCE(a.ai_token_count, 0) AS ai_token_count,
            CAST(0 AS INT64) AS storage_bytes
        FROM all_keys k
        LEFT JOIN bq_jobs q
            ON k.usage_date = q.usage_date AND k.room_id = q.room_id AND k.user_email = q.user_email
        LEFT JOIN notebook_hours n
            ON k.usage_date = n.usage_date AND k.room_id = n.room_id AND k.user_email = n.user_email
        LEFT JOIN ai_usage a
            ON k.usage_date = a.usage_date AND k.room_id = a.room_id AND k.user_email = a.user_email
        LEFT JOIN `hub_registry.reg_research_rooms` r
            ON k.room_id = r.room_id
    )
    SELECT * FROM combined;
END;

-- 3. Table: ops_monthly_usage_rollup
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_monthly_usage_rollup` (
    usage_month DATE NOT NULL,
    room_id STRING NOT NULL,
    institute_id STRING NOT NULL,
    avg_active_researchers NUMERIC,
    total_notebook_hours NUMERIC,
    total_query_volume_tb NUMERIC,
    total_slot_hours NUMERIC
)
PARTITION BY usage_month
CLUSTER BY room_id, institute_id
OPTIONS(
    description = 'Monthly rollup of compute, active researchers, and query volume per room'
);

-- 4. Stored Procedure: sp_rollup_monthly_usage
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_rollup_monthly_usage`()
BEGIN
    TRUNCATE TABLE `hub_telemetry.ops_monthly_usage_rollup`;
    INSERT INTO `hub_telemetry.ops_monthly_usage_rollup` (
        usage_month, room_id, institute_id, avg_active_researchers,
        total_notebook_hours, total_query_volume_tb, total_slot_hours
    )
    SELECT
        DATE_TRUNC(usage_date, MONTH) AS usage_month,
        room_id,
        COALESCE(institute_id, 'inst-unknown') AS institute_id,
        CAST(ROUND(COUNT(DISTINCT user_email) / GREATEST(COUNT(DISTINCT usage_date), 1), 2) AS NUMERIC) AS avg_active_researchers,
        CAST(ROUND(SUM(COALESCE(notebook_runtime_hours, 0)), 2) AS NUMERIC) AS total_notebook_hours,
        CAST(ROUND(SUM(COALESCE(total_bytes_billed, 0)) / (1024.0 * 1024.0 * 1024.0 * 1024.0), 5) AS NUMERIC) AS total_query_volume_tb,
        CAST(ROUND(SUM(COALESCE(total_slot_hours, 0)), 5) AS NUMERIC) AS total_slot_hours
    FROM `hub_telemetry.ops_daily_compute_metrics`
    GROUP BY 1, 2, 3;
END;
