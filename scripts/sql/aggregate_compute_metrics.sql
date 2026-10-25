-- scripts/sql/aggregate_compute_metrics.sql
-- Production Telemetry Engine: Compute, BigQuery, Storage, and AI Usage Aggregations
-- Replaces destructive TRUNCATE with idempotent MERGE and preserves historical continuity

-- 1. Table: ops_daily_compute_metrics (Unified Daily Mart)
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

-- 2. Table: ops_storage_daily (Attributed GCS Storage Detail per Researcher & Bucket)
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_storage_daily` (
    usage_date DATE NOT NULL,
    room_id STRING NOT NULL,
    user_email STRING NOT NULL,
    bucket_name STRING NOT NULL,
    storage_bytes INT64 NOT NULL,
    file_count INT64,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY usage_date
CLUSTER BY room_id, user_email
OPTIONS(
    description = 'Daily physical Cloud Storage bytes and file counts attributed per researcher and bucket'
);

-- 3. Table: raw_storage_inventory (Direct Landing from GCS Storage Insights Daily Inventory Drop)
CREATE TABLE IF NOT EXISTS `hub_telemetry.raw_storage_inventory` (
    snapshot_date DATE NOT NULL,
    bucket STRING NOT NULL,
    name STRING NOT NULL,
    size INT64 NOT NULL,
    storage_class STRING,
    time_created TIMESTAMP,
    updated TIMESTAMP,
    content_type STRING
)
PARTITION BY snapshot_date
CLUSTER BY bucket
OPTIONS(
    description = 'Raw GCS Storage Insights daily inventory export of physical object manifests'
);

-- 4. Table: ops_bigquery_usage_15m (15-Minute BigQuery Query Execution Mart)
CREATE TABLE IF NOT EXISTS `hub_telemetry.ops_bigquery_usage_15m` (
    usage_date DATE NOT NULL,
    room_id STRING NOT NULL,
    user_email STRING NOT NULL,
    query_count INT64,
    total_bytes_billed INT64,
    total_slot_hours NUMERIC,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY usage_date
CLUSTER BY room_id, user_email
OPTIONS(
    description = '15-minute aggregated BigQuery job metrics from INFORMATION_SCHEMA and curated audit trail'
);

-- 5. Procedure: sp_sync_bigquery_queries (15-minute Spoke INFORMATION_SCHEMA Query Ingestion)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_sync_bigquery_queries`()
BEGIN
    DECLARE projects ARRAY<STRUCT<room_id STRING, spoke_project_id STRING>>;
    DECLARE i INT64 DEFAULT 0;
    DECLARE curr_room STRING;
    DECLARE curr_spoke STRING;
    DECLARE sql_stmt STRING;

    SET projects = ARRAY(
        SELECT AS STRUCT room_id, spoke_project_id 
        FROM `hub_registry.reg_research_rooms` 
        WHERE spoke_project_id IS NOT NULL
    );

    WHILE i < ARRAY_LENGTH(projects) DO
        SET curr_room = projects[OFFSET(i)].room_id;
        SET curr_spoke = projects[OFFSET(i)].spoke_project_id;
        
        SET sql_stmt = FORMAT("""
            MERGE `hub_telemetry.ops_bigquery_usage_15m` T
            USING (
                SELECT
                    '%s' AS room_id,
                    user_email,
                    DATE(start_time) AS usage_date,
                    COUNT(1) AS query_count,
                    SUM(COALESCE(total_bytes_billed, total_bytes_processed, 0)) AS total_bytes_billed,
                    CAST(ROUND(SUM(COALESCE(total_slot_ms, 0)) / 3600000.0, 5) AS NUMERIC) AS total_slot_hours
                FROM `%s.region-me-west1.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                WHERE job_type = 'QUERY'
                  AND start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 35 MINUTE)
                  AND user_email IS NOT NULL
                GROUP BY 1, 2, 3
            ) S
            ON T.usage_date = S.usage_date AND T.room_id = S.room_id AND T.user_email = S.user_email
            WHEN MATCHED THEN
                UPDATE SET
                    query_count = T.query_count + S.query_count,
                    total_bytes_billed = T.total_bytes_billed + S.total_bytes_billed,
                    total_slot_hours = T.total_slot_hours + S.total_slot_hours,
                    last_updated = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (usage_date, room_id, user_email, query_count, total_bytes_billed, total_slot_hours, last_updated)
                VALUES (S.usage_date, S.room_id, S.user_email, S.query_count, S.total_bytes_billed, S.total_slot_hours, CURRENT_TIMESTAMP());
        """, curr_room, curr_spoke);

        EXECUTE IMMEDIATE sql_stmt;
        SET i = i + 1;
    END WHILE;
END;

-- 6. Procedure: sp_sync_storage_metrics (Daily Storage Attribution from GCS Inventory & Audit Events)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_sync_storage_metrics`()
BEGIN
    -- Dynamically correlate GCS Storage Insights inventory with object creation audit records
    MERGE `hub_telemetry.ops_storage_daily` T
    USING (
        WITH latest_inv AS (
            SELECT bucket, name, size
            FROM `hub_telemetry.raw_storage_inventory`
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `hub_telemetry.raw_storage_inventory`)
        ),
        creators AS (
            SELECT
                resource_name,
                principal_email AS user_email,
                room_id,
                ROW_NUMBER() OVER(PARTITION BY resource_name ORDER BY timestamp DESC) as rn
            FROM `hub_telemetry.ops_audit_events_curated`
            WHERE service_name = 'storage.googleapis.com'
              AND action_name = 'storage.objects.create'
        ),
        object_attribution AS (
            SELECT
                CURRENT_DATE() AS usage_date,
                COALESCE(c.room_id, rr.room_id, 'rr-unknown') AS room_id,
                COALESCE(c.user_email, 'shared-storage') AS user_email,
                i.bucket AS bucket_name,
                i.size AS object_bytes
            FROM latest_inv i
            LEFT JOIN creators c
                ON c.resource_name = CONCAT('projects/_/buckets/', i.bucket, '/objects/', i.name)
               AND c.rn = 1
            LEFT JOIN `hub_registry.reg_research_rooms` rr
                ON rr.inbound_bucket = CONCAT('gs://', i.bucket)
                OR rr.export_bucket = CONCAT('gs://', i.bucket)
        )
        SELECT
            usage_date,
            room_id,
            user_email,
            bucket_name,
            SUM(object_bytes) AS storage_bytes,
            COUNT(1) AS file_count
        FROM object_attribution
        GROUP BY 1, 2, 3, 4
    ) S
    ON T.usage_date = S.usage_date AND T.room_id = S.room_id AND T.user_email = S.user_email AND T.bucket_name = S.bucket_name
    WHEN MATCHED THEN
        UPDATE SET
            storage_bytes = S.storage_bytes,
            file_count = S.file_count,
            last_updated = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN
        INSERT (usage_date, room_id, user_email, bucket_name, storage_bytes, file_count, last_updated)
        VALUES (S.usage_date, S.room_id, S.user_email, S.bucket_name, S.storage_bytes, S.file_count, CURRENT_TIMESTAMP());
END;

-- 7. Stored Procedure: sp_aggregate_daily_compute_metrics (Idempotent MERGE without TRUNCATE)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_aggregate_daily_compute_metrics`()
BEGIN
    MERGE `hub_telemetry.ops_daily_compute_metrics` T
    USING (
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
                        SAFE_CAST(JSON_VALUE(metadata_json, '$.jobChange.after.jobStats.queryStats.totalProcessedBytes') AS INT64),
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
                SUM(COALESCE(ai_token_count, total_inference_calls * 1500)) AS ai_token_count
            FROM `hub_telemetry.ops_ai_usage_metrics`
            GROUP BY 1, 2, 3
        ),
        storage_usage AS (
            SELECT
                room_id,
                user_email,
                usage_date,
                SUM(storage_bytes) AS storage_bytes
            FROM `hub_telemetry.ops_storage_daily`
            GROUP BY 1, 2, 3
        ),
        all_keys AS (
            SELECT room_id, user_email, usage_date FROM bq_jobs WHERE room_id IS NOT NULL
            UNION DISTINCT
            SELECT room_id, user_email, usage_date FROM notebook_hours WHERE room_id IS NOT NULL
            UNION DISTINCT
            SELECT room_id, user_email, usage_date FROM ai_usage WHERE room_id IS NOT NULL
            UNION DISTINCT
            SELECT room_id, user_email, usage_date FROM storage_usage WHERE room_id IS NOT NULL
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
                s.storage_bytes AS storage_bytes
            FROM all_keys k
            LEFT JOIN bq_jobs q
                ON k.usage_date = q.usage_date AND k.room_id = q.room_id AND k.user_email = q.user_email
            LEFT JOIN notebook_hours n
                ON k.usage_date = n.usage_date AND k.room_id = n.room_id AND k.user_email = n.user_email
            LEFT JOIN ai_usage a
                ON k.usage_date = a.usage_date AND k.room_id = a.room_id AND k.user_email = a.user_email
            LEFT JOIN storage_usage s
                ON k.usage_date = s.usage_date AND k.room_id = s.room_id AND k.user_email = s.user_email
            LEFT JOIN `hub_registry.reg_research_rooms` r
                ON k.room_id = r.room_id
        )
        SELECT * FROM combined
    ) S
    ON T.usage_date = S.usage_date AND T.room_id = S.room_id AND T.user_email = S.user_email
    WHEN MATCHED THEN
        UPDATE SET
            query_count = S.query_count,
            total_bytes_billed = S.total_bytes_billed,
            total_slot_hours = S.total_slot_hours,
            notebook_runtime_hours = S.notebook_runtime_hours,
            ai_inference_count = S.ai_inference_count,
            ai_token_count = S.ai_token_count,
            -- PRESERVE existing storage_bytes if today's storage has not arrived yet:
            storage_bytes = COALESCE(S.storage_bytes, T.storage_bytes, 0),
            institute_id = S.institute_id
    WHEN NOT MATCHED THEN
        INSERT (usage_date, room_id, user_email, institute_id, query_count, total_bytes_billed, total_slot_hours, notebook_runtime_hours, ai_inference_count, ai_token_count, storage_bytes)
        VALUES (S.usage_date, S.room_id, S.user_email, S.institute_id, S.query_count, S.total_bytes_billed, S.total_slot_hours, S.notebook_runtime_hours, S.ai_inference_count, S.ai_token_count, COALESCE(S.storage_bytes, 0));
END;

-- 8. Table: ops_monthly_usage_rollup (Executive & Governance Monthly Rollup)
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

-- 9. Stored Procedure: sp_rollup_monthly_usage (Idempotent MERGE without TRUNCATE)
CREATE OR REPLACE PROCEDURE `hub_telemetry.sp_rollup_monthly_usage`()
BEGIN
    MERGE `hub_telemetry.ops_monthly_usage_rollup` T
    USING (
        SELECT
            DATE_TRUNC(usage_date, MONTH) AS usage_month,
            room_id,
            COALESCE(institute_id, 'inst-unknown') AS institute_id,
            CAST(ROUND(COUNT(DISTINCT user_email) / GREATEST(COUNT(DISTINCT usage_date), 1), 2) AS NUMERIC) AS avg_active_researchers,
            CAST(ROUND(SUM(COALESCE(notebook_runtime_hours, 0)), 2) AS NUMERIC) AS total_notebook_hours,
            CAST(ROUND(SUM(COALESCE(total_bytes_billed, 0)) / (1024.0 * 1024.0 * 1024.0 * 1024.0), 5) AS NUMERIC) AS total_query_volume_tb,
            CAST(ROUND(SUM(COALESCE(total_slot_hours, 0)), 5) AS NUMERIC) AS total_slot_hours
        FROM `hub_telemetry.ops_daily_compute_metrics`
        GROUP BY 1, 2, 3
    ) S
    ON T.usage_month = S.usage_month AND T.room_id = S.room_id AND T.institute_id = S.institute_id
    WHEN MATCHED THEN
        UPDATE SET
            avg_active_researchers = S.avg_active_researchers,
            total_notebook_hours = S.total_notebook_hours,
            total_query_volume_tb = S.total_query_volume_tb,
            total_slot_hours = S.total_slot_hours
    WHEN NOT MATCHED THEN
        INSERT (usage_month, room_id, institute_id, avg_active_researchers, total_notebook_hours, total_query_volume_tb, total_slot_hours)
        VALUES (S.usage_month, S.room_id, S.institute_id, S.avg_active_researchers, S.total_notebook_hours, S.total_query_volume_tb, S.total_slot_hours);
END;
