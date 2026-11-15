# Keep bad rows out of the way with DML error logging

topics: copy-into, pipeline-design, migration-strategy
tags: data-quality, error-handling, dml
level: intermediate

Normally a single bad value fails the whole INSERT, UPDATE or MERGE. With `ERROR_LOGGING = TRUE`, valid rows are written and failing rows go to an error table, where you can inspect, fix and replay them. This is similar to Oracle's LOG ERRORS clause.

```sql
USE SCHEMA my_db.my_schema;
USE WAREHOUSE my_wh;

-- 1. Base table with error logging enabled
CREATE OR REPLACE TABLE orders_clean (
  order_id  NUMBER(10,0) NOT NULL,
  amount    NUMBER(12,2),
  status    VARCHAR(10)
) ERROR_LOGGING = TRUE;
-- or: ALTER TABLE existing_table SET ERROR_LOGGING = TRUE;

-- 2. Raw data containing a cast error, a NULL key and a too-long string
CREATE OR REPLACE TEMPORARY TABLE orders_raw (order_id STRING, amount STRING, status STRING);
INSERT INTO orders_raw VALUES
  ('1', '19.99', 'shipped'),
  ('2', 'abc',   'new'),
  (NULL, '5.00', 'new'),
  ('4', '7.50',  'cancelled_by_customer');

-- Only the valid row is inserted; the others are logged
INSERT INTO orders_clean SELECT order_id, amount, status FROM orders_raw;

-- 3. Review the errors
SELECT timestamp,
       query_id,
       error_code,
       error_metadata:error_message::STRING AS message,
       error_metadata:error_source::STRING  AS column_name,
       error_data
FROM ERROR_TABLE(orders_clean)
ORDER BY timestamp DESC;

-- 4. Summary per error type
SELECT error_metadata:error_message::STRING AS message, COUNT(*) AS n
FROM ERROR_TABLE(orders_clean)
GROUP BY 1 ORDER BY n DESC;

-- 5. Let an analyst role read the errors
GRANT SELECT ERROR TABLE ON TABLE orders_clean TO ROLE my_analyst_role;

-- 6. After fixing/replaying, clear the error table
TRUNCATE ERROR_TABLE(orders_clean);

-- Opt out for one session (statements fail normally again)
ALTER SESSION SET OPT_OUT_ERROR_LOGGING = TRUE;
```

## Notes
- Logs errors for INSERT, UPDATE and MERGE: NOT NULL violations, type conversion errors, precision or length overflows, and some expression failures such as division by zero.
- COPY INTO a table with error logging enabled fails at compile time. Keep using ON_ERROR and VALIDATE for COPY loads. CTAS statements also do not log errors.
- You can only SELECT from or TRUNCATE an error table. To track it with a stream, create a view on the error table and put the stream on the view.
- Turning off ERROR_LOGGING or dropping the base table also drops its error table. The error table uses normal storage.

## References
- [Overview of data loading: DML error logging](https://docs.snowflake.com/en/user-guide/data-load-overview)
- [ALTER TABLE](https://docs.snowflake.com/en/sql-reference/sql/alter-table)
