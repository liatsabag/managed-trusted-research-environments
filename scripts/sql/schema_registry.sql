-- scripts/sql/schema_registry.sql
-- Hub Operational Registry & Directory Schemas

CREATE SCHEMA IF NOT EXISTS `hub_registry`
OPTIONS(
  location = 'me-west1',
  description = 'Central Administrator Registry for institutes, researchers, and research rooms'
);

-- 1. Institutes Table
CREATE TABLE IF NOT EXISTS `hub_registry.reg_institutes` (
    institute_id STRING NOT NULL,
    name STRING NOT NULL,
    country STRING DEFAULT 'USA',
    contact_email STRING NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 2. Researchers Table
CREATE TABLE IF NOT EXISTS `hub_registry.reg_researchers` (
    researcher_id STRING NOT NULL,
    first_name STRING NOT NULL,
    last_name STRING NOT NULL,
    primary_email STRING NOT NULL,
    role STRING NOT NULL,
    access_state STRING NOT NULL,
    org_unit_path STRING NOT NULL,
    institute_id STRING NOT NULL,
    room_id STRING NOT NULL,
    cloud_identity_group STRING NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 3. Research Rooms Table
CREATE TABLE IF NOT EXISTS `hub_registry.reg_research_rooms` (
    room_id STRING NOT NULL,
    room_name STRING NOT NULL,
    institute_id STRING NOT NULL,
    spoke_project_id STRING NOT NULL,
    status STRING DEFAULT 'ACTIVE',
    helsinki_expiry_date DATE NOT NULL,
    dua_expiry_date DATE NOT NULL,
    inbound_bucket STRING NOT NULL,
    export_bucket STRING NOT NULL,
    cloud_identity_group STRING NOT NULL,
    tables_count INT64 DEFAULT 0,
    lead_researcher_id STRING,
    lead_researcher_email STRING,
    budget_limit_usd NUMERIC DEFAULT 5000.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 4. Room Installed Packages Table
CREATE TABLE IF NOT EXISTS `hub_registry.reg_room_packages` (
    room_id STRING NOT NULL,
    runtime_id STRING NOT NULL,
    package_name STRING NOT NULL,
    package_version STRING NOT NULL,
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
