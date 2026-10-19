-- scripts/sql/schema_billing_export.sql
-- Base GCP Billing Export Table DDL in billing dataset

CREATE SCHEMA IF NOT EXISTS `billing`
OPTIONS(
  location = 'me-west1',
  description = 'GCP Detailed Cloud Billing Export Dataset'
);

CREATE TABLE IF NOT EXISTS `billing.gcp_billing_export_v1` (
    billing_account_id STRING,
    service STRUCT<id STRING, description STRING>,
    sku STRUCT<id STRING, description STRING>,
    usage_start_time TIMESTAMP,
    usage_end_time TIMESTAMP,
    project STRUCT<id STRING, name STRING, labels ARRAY<STRUCT<key STRING, value STRING>>, ancestry_numbers STRING>,
    labels ARRAY<STRUCT<key STRING, value STRING>>,
    system_labels ARRAY<STRUCT<key STRING, value STRING>>,
    location STRUCT<location STRING, country STRING, region STRING, zone STRING>,
    export_time TIMESTAMP,
    cost FLOAT64,
    currency STRING,
    currency_conversion_rate FLOAT64,
    usage STRUCT<amount FLOAT64, unit STRING, amount_in_pricing_units FLOAT64, pricing_unit STRING>,
    credits ARRAY<STRUCT<name STRING, amount FLOAT64, full_name STRING, id STRING, type STRING>>,
    invoice STRUCT<month STRING>,
    cost_type STRING,
    adjustment_info STRUCT<id STRING, mode STRING, type STRING, description STRING>
);
