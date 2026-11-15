# Dry-run, load, and audit a COPY INTO

topics: copy-into, file-formats, account-usage
tags: loading, validation, data-quality
level: beginner

Check staged files for errors before loading, load while skipping bad rows, then review what was rejected and the per-file load history.

```sql
USE SCHEMA my_db.my_schema;
USE WAREHOUSE my_wh;

CREATE OR REPLACE FILE FORMAT csv_fmt
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('', 'NULL');

CREATE TABLE IF NOT EXISTS customers (
  id INT NOT NULL, name STRING, email STRING, signup_date DATE
);

-- 1. Dry run: return every parsing error without loading anything
COPY INTO customers
  FROM @my_stage/customers/
  FILE_FORMAT = (FORMAT_NAME = 'csv_fmt')
  VALIDATION_MODE = RETURN_ERRORS;

-- Or preview the first rows as they would be parsed
COPY INTO customers
  FROM @my_stage/customers/
  FILE_FORMAT = (FORMAT_NAME = 'csv_fmt')
  VALIDATION_MODE = RETURN_10_ROWS;

-- 2. Real load: skip bad rows but give up on a file that is more than 5% bad
COPY INTO customers
  FROM @my_stage/customers/
  FILE_FORMAT = (FORMAT_NAME = 'csv_fmt')
  ON_ERROR = 'SKIP_FILE_5%';

-- Alternative: keep every good row from every file
-- ON_ERROR = CONTINUE

-- 3. Rows rejected by the most recent COPY in this session
SELECT * FROM TABLE(VALIDATE(customers, JOB_ID => '_last'));

-- 4. Per-file outcome for the last 24 hours (INFORMATION_SCHEMA, no latency)
SELECT file_name, status, row_count, row_parsed, error_count,
       first_error_message, first_error_line_number, last_load_time
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
       TABLE_NAME => 'CUSTOMERS',
       START_TIME => DATEADD(hour, -24, CURRENT_TIMESTAMP())))
ORDER BY last_load_time DESC;

-- 5. Longer-term trend from ACCOUNT_USAGE (up to ~2h latency)
SELECT DATE_TRUNC('day', last_load_time) AS load_day,
       status,
       COUNT(*)         AS files,
       SUM(row_count)   AS rows_loaded,
       SUM(error_count) AS rows_rejected
FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
WHERE table_name = 'CUSTOMERS'
  AND last_load_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY 1 DESC;
```

## Notes
- VALIDATION_MODE does not work with COPY statements that transform data (`COPY INTO t FROM (SELECT ...)`).
- VALIDATE only returns errors for COPY jobs run with ON_ERROR = CONTINUE or SKIP_FILE. Pass `'_last'` or the query ID of a specific COPY job.
- COPY keeps load metadata for 64 days and skips files it has already loaded. Use `FORCE = TRUE` only when you really want to reload them, because it creates duplicates.

## References
- [COPY INTO <table>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)
- [VALIDATE](https://docs.snowflake.com/en/sql-reference/functions/validate)
- [COPY_HISTORY table function](https://docs.snowflake.com/en/sql-reference/functions/copy_history)
