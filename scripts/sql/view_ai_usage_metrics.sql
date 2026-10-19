-- scripts/sql/view_ai_usage_metrics.sql
-- Vertex AI & Gemini Telemetry View: Tracks AI inference invocations per (room_id, user_email)

CREATE OR REPLACE VIEW `hub_telemetry.view_ai_usage_metrics` AS
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
        severity
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
    COUNTIF(status = 'SUCCESS') AS successful_calls,
    COUNTIF(status != 'SUCCESS') AS failed_calls,
    MIN(timestamp) AS first_invoked_at,
    MAX(timestamp) AS last_invoked_at
FROM ai_events
GROUP BY room_id, project_id, user_email, usage_date, service_name;
