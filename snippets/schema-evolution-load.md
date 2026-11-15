# Auto-create a table from Parquet and let it evolve

topics: infer-schema, copy-into
tags: loading, schema-evolution, parquet
level: intermediate

Build the table directly from the files' own schema with INFER_SCHEMA and USING TEMPLATE. Then turn on schema evolution so later files that add columns load without a manual ALTER TABLE.

```sql
USE SCHEMA my_db.my_schema;
USE WAREHOUSE my_wh;

CREATE OR REPLACE FILE FORMAT parquet_fmt TYPE = PARQUET;

-- 1. See what Snowflake detects
SELECT column_name, type, nullable, expression
FROM TABLE(INFER_SCHEMA(
       LOCATION    => '@my_stage/events/',
       FILE_FORMAT => 'parquet_fmt'));

-- 2. Create the table from the detected columns, with evolution enabled
CREATE OR REPLACE TABLE events
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*)) WITHIN GROUP (ORDER BY order_id)
    FROM TABLE(INFER_SCHEMA(
           LOCATION    => '@my_stage/events/',
           FILE_FORMAT => 'parquet_fmt'))
  )
  ENABLE_SCHEMA_EVOLUTION = TRUE;

-- 3. Load by column name; new columns in later files are added automatically
COPY INTO events
  FROM @my_stage/events/
  FILE_FORMAT = (FORMAT_NAME = 'parquet_fmt')
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

-- 4. Inspect what changed (evolved columns are recorded in SCHEMA_EVOLUTION_RECORD)
SELECT column_name, data_type, schema_evolution_record
FROM INFORMATION_SCHEMA.COLUMNS
WHERE table_schema = 'MY_SCHEMA' AND table_name = 'EVENTS'
ORDER BY ordinal_position;

-- Turn evolution on/off for an existing table
ALTER TABLE events SET ENABLE_SCHEMA_EVOLUTION = FALSE;

-- CSV variant: INFER_SCHEMA needs PARSE_HEADER = TRUE in the file format
CREATE OR REPLACE FILE FORMAT csv_hdr_fmt
  TYPE = CSV
  PARSE_HEADER = TRUE
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;   -- required for CSV schema evolution
```

## Notes
- The role loading the data needs the EVOLVE SCHEMA privilege on the table, or must own it.
- Schema evolution adds new columns and drops NOT NULL constraints when a column is missing from new files. It does not change data types.
- It needs `MATCH_BY_COLUMN_NAME` with COPY or Snowpipe. For CSV, the file format also needs `PARSE_HEADER = TRUE` and `ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE`.
- INFER_SCHEMA scans files, so point it at a representative subset (use `FILES =` or `MAX_FILE_COUNT`) when the location is large.

## References
- [INFER_SCHEMA](https://docs.snowflake.com/en/sql-reference/functions/infer_schema)
- [Table schema evolution](https://docs.snowflake.com/en/user-guide/data-load-schema-evolution)
- [CREATE TABLE ... USING TEMPLATE](https://docs.snowflake.com/en/sql-reference/sql/create-table)
