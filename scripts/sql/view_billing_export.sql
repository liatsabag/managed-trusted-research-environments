-- scripts/sql/view_billing_export.sql
-- Authorized Billing Export View filtering Research Room Fleet Projects

CREATE OR REPLACE VIEW `hub_telemetry.view_billing_export`
OPTIONS(
  description = 'Authorized view filtering GCP Cloud Billing export records for active Research Room spoke projects'
) AS
SELECT
    billing_account_id,
    service.id AS service_id,
    service.description AS service_description,
    sku.id AS sku_id,
    sku.description AS sku_description,
    usage_start_time,
    usage_end_time,
    CASE project.id
        WHEN 'tre-room-cardio-353306' THEN 'gcp-rr-spoke-cardio-03'
        WHEN 'tre-room-onco-353306' THEN 'gcp-rr-spoke-oncology-01'
        WHEN 'tre-room-genom-353306' THEN 'gcp-rr-spoke-genomics-02'
        WHEN 'tre-room-neuro-353306' THEN 'gcp-rr-spoke-neurology-04'
        ELSE project.id
    END AS project_id,
    project.name AS project_name,
    project.labels,
    location.location AS location,
    location.country AS country,
    location.region AS region,
    location.zone AS zone,
    cost,
    currency,
    usage.amount AS usage_amount,
    usage.unit AS usage_unit,
    usage.amount_in_pricing_units AS usage_amount_in_pricing_units,
    usage.pricing_unit AS pricing_unit,
    credits,
    invoice.month AS invoice_month,
    cost_type,
    adjustment_info
FROM
    `gcp-billing-export-sink.billing.gcp_billing_export_v1`
WHERE
    project.id LIKE 'gcp-rr-%'
    OR project.id LIKE 'tre-room-%';
