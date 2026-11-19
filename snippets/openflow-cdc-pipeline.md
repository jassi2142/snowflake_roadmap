# Openflow streaming CDC pipeline into dynamic tables

topics: openflow, dynamic-tables, pipeline-design
tags: openflow, cdc, streaming, ingestion
level: intermediate

A production pattern for real-time change data capture (CDC) using Snowflake Openflow. Openflow streams change records from transactional databases into an append-only landing table, while a downstream Dynamic Table automatically merges inserts, updates, and deletes into a current-state table.

```sql
-- 1. Create target schemas and execution role
CREATE DATABASE IF NOT EXISTS cdc_pipeline_db;
CREATE SCHEMA IF NOT EXISTS cdc_pipeline_db.raw_landing;
CREATE SCHEMA IF NOT EXISTS cdc_pipeline_db.curated;

-- 2. Raw landing table for Openflow CDC FlowFiles
CREATE OR REPLACE TABLE cdc_pipeline_db.raw_landing.customer_cdc (
  record_id     NUMBER AUTOINCREMENT,
  source_op     VARCHAR(10),            -- 'INSERT', 'UPDATE', 'DELETE'
  source_ts     TIMESTAMP_NTZ,
  payload       VARIANT,                -- Full row state in JSON
  ingested_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 3. Openflow Gen 2 Runtime definition
-- Openflow connectors deliver CDC records directly to customer_cdc
CREATE OPENFLOW RUNTIME cdc_pipeline_db.raw_landing.pg_cdc_runtime
  IN DEPLOYMENT prod_openflow_spcs_deployment
  EXECUTE AS ROLE cdc_ingest_role
  COMMENT = 'Manages real-time PostgreSQL CDC connector';

-- 4. Dynamic Table for automated state reconstruction
CREATE OR REPLACE DYNAMIC TABLE cdc_pipeline_db.curated.customers_current
  TARGET_LAG = '1 MINUTE'
  WAREHOUSE = transform_wh
AS
WITH ranked_changes AS (
  SELECT
    payload:id::INT              AS customer_id,
    payload:first_name::STRING   AS first_name,
    payload:last_name::STRING    AS last_name,
    payload:email::STRING        AS email,
    payload:tier::STRING         AS membership_tier,
    source_op,
    source_ts,
    ROW_NUMBER() OVER (
      PARTITION BY payload:id::INT
      ORDER BY source_ts DESC, record_id DESC
    ) AS row_rank
  FROM cdc_pipeline_db.raw_landing.customer_cdc
)
SELECT
  customer_id,
  first_name,
  last_name,
  email,
  membership_tier,
  source_ts AS last_updated_at
FROM ranked_changes
WHERE row_rank = 1
  AND source_op != 'DELETE';

-- 5. Monitor pipeline latency and refresh history
SELECT
  name,
  state,
  last_completed_refresh,
  target_lag,
  actual_lag
FROM TABLE(INFORMATION_SCHEMA.DYNAMIC_TABLES())
WHERE name = 'CUSTOMERS_CURRENT';
```
