# Attach system DMFs with expectations and read the results

topics: data-metric-functions
tags: data-quality, monitoring, dmf
level: advanced

Monitor an orders table for NULL customer ids, duplicate order ids and stale loads with Snowflake's built-in data metric functions (DMFs). Expectations set the pass/fail threshold, so you can query for violations instead of judging raw numbers.

```sql
USE ROLE dq_engineer;   -- owns the table and has EXECUTE DATA METRIC FUNCTION on the account
USE SCHEMA my_db.sales;

-- 1. Set the table's schedule first; it applies to every DMF on the table.
--    Options: 'n MINUTE' (5, 15, 30, 60, 720, 1440), 'USING CRON ...', or 'TRIGGER_ON_CHANGES'
ALTER TABLE orders SET DATA_METRIC_SCHEDULE = 'USING CRON 0 * * * * UTC';   -- hourly

-- 2. Attach system DMFs, each with an expectation
ALTER TABLE orders
  ADD DATA METRIC FUNCTION SNOWFLAKE.CORE.NULL_COUNT ON (customer_id)
  EXPECTATION no_null_customers (VALUE = 0);

ALTER TABLE orders
  ADD DATA METRIC FUNCTION SNOWFLAKE.CORE.DUPLICATE_COUNT ON (order_id)
  EXPECTATION unique_order_ids (VALUE = 0);

-- FRESHNESS returns seconds since the latest value in the timestamp column
ALTER TABLE orders
  ADD DATA METRIC FUNCTION SNOWFLAKE.CORE.FRESHNESS ON (loaded_at)
  EXPECTATION loaded_within_2h (VALUE < 7200);

-- 3. Check the associations and the schedule
SELECT metric_name, ref_arguments, schedule, schedule_status
FROM TABLE(INFORMATION_SCHEMA.DATA_METRIC_FUNCTION_REFERENCES(
       REF_ENTITY_NAME => 'my_db.sales.orders', REF_ENTITY_DOMAIN => 'TABLE'));

-- 4. Evaluate expectations now instead of waiting for the schedule
SELECT *
FROM TABLE(SYSTEM$EVALUATE_DATA_QUALITY_EXPECTATIONS(
       REF_ENTITY_NAME => 'my_db.sales.orders'));

-- 5. Historical measurements written by the schedule
SELECT measurement_time, metric_name, argument_names, value
FROM SNOWFLAKE.LOCAL.DATA_QUALITY_MONITORING_RESULTS
WHERE table_database = 'MY_DB' AND table_schema = 'SALES' AND table_name = 'ORDERS'
  AND measurement_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY measurement_time DESC;

-- 6. Expectation pass/fail history
SELECT *
FROM SNOWFLAKE.LOCAL.DATA_QUALITY_MONITORING_EXPECTATION_STATUS
LIMIT 100;

-- Change a threshold later
-- ALTER TABLE orders MODIFY DATA METRIC FUNCTION SNOWFLAKE.CORE.FRESHNESS ON (loaded_at)
--   MODIFY EXPECTATION loaded_within_2h (VALUE < 10800);

-- Clean up
-- ALTER TABLE orders DROP DATA METRIC FUNCTION SNOWFLAKE.CORE.NULL_COUNT ON (customer_id);
-- ALTER TABLE orders UNSET DATA_METRIC_SCHEDULE;
```

## Notes
- Requires Enterprise Edition or higher. DMFs run on serverless compute, so very frequent schedules on large tables add up.
- One schedule applies to every DMF on a table. `TRIGGER_ON_CHANGES` runs the DMFs after DML changes the table, not on a timer.
- Reading `SNOWFLAKE.LOCAL.DATA_QUALITY_MONITORING_RESULTS` requires a role with the SNOWFLAKE.DATA_QUALITY_MONITORING_VIEWER or SNOWFLAKE.DATA_QUALITY_MONITORING_ADMIN application role.
- In an expectation, `VALUE` is the DMF result. Expressions can use comparison and logical operators but can't reference other tables or UDFs.
- To act on failures automatically, put an alert on top of the expectation-status view.

## References
- [Use SQL to set up data metric functions](https://docs.snowflake.com/en/user-guide/data-quality-working)
- [Use SQL to work with expectations](https://docs.snowflake.com/en/user-guide/data-quality-expectations)
- [System data metric functions](https://docs.snowflake.com/en/user-guide/data-quality-system-dmfs)
