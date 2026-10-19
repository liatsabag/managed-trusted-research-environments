-- scripts/sql/view_notebook_session_metrics.sql
-- Notebook & Compute Sessionization View: Aggregates runtime lifecycles into daily active hours per (room_id, user_email)

CREATE OR REPLACE VIEW `hub_telemetry.view_notebook_session_metrics` AS
WITH session_events AS (
    SELECT
        room_id,
        principal_email AS user_email,
        DATE(timestamp) AS session_date,
        log_id,
        timestamp,
        action_name,
        category,
        status
    FROM `hub_telemetry.ops_audit_events_curated`
    WHERE category = 'COMPUTE_SESSION'
       OR LOWER(service_name) LIKE '%notebooks%'
       OR LOWER(service_name) LIKE '%compute%'
       OR LOWER(action_name) LIKE '%instance%'
       OR LOWER(action_name) LIKE '%session%'
),
session_aggregates AS (
    SELECT
        room_id,
        user_email,
        session_date,
        COUNT(DISTINCT log_id) AS total_events,
        COUNT(DISTINCT IF(LOWER(action_name) LIKE '%start%' OR LOWER(action_name) LIKE '%create%', log_id, NULL)) AS session_starts,
        COUNT(DISTINCT IF(LOWER(action_name) LIKE '%stop%' OR LOWER(action_name) LIKE '%delete%', log_id, NULL)) AS session_stops,
        MIN(timestamp) AS first_session_start,
        MAX(timestamp) AS last_session_end,
        ROUND(
            GREATEST(
                COUNT(DISTINCT log_id) * 0.5,
                TIMESTAMP_DIFF(MAX(timestamp), MIN(timestamp), MINUTE) / 60.0
            ),
            2
        ) AS estimated_active_hours
    FROM session_events
    GROUP BY room_id, user_email, session_date
)
SELECT
    room_id,
    user_email,
    session_date,
    total_events,
    session_starts,
    session_stops,
    GREATEST(session_starts, 1) AS total_sessions,
    estimated_active_hours AS total_active_hours,
    first_session_start,
    last_session_end
FROM session_aggregates;
