# Bronze, silver, gold pipeline with dynamic tables

topics: dynamic-tables, medallion-architecture
tags: elt, pipelines, sql
level: intermediate

Declare each layer as a dynamic table and let Snowflake schedule refreshes. Intermediate layers use `TARGET_LAG = DOWNSTREAM` so they refresh only when the gold table needs them.

```sql
USE SCHEMA my_db.pipelines;

-- Silver: parse and clean raw JSON events
CREATE OR REPLACE DYNAMIC TABLE silver_orders
  TARGET_LAG = DOWNSTREAM
  WAREHOUSE = my_wh
  REFRESH_MODE = INCREMENTAL
AS
SELECT
  raw:order_id::NUMBER          AS order_id,
  raw:customer_id::NUMBER       AS customer_id,
  raw:amount::NUMBER(12,2)      AS amount,
  raw:order_ts::TIMESTAMP_NTZ   AS order_ts
FROM my_db.bronze.raw_orders           -- bronze: landing table loaded by COPY/Snowpipe
WHERE raw:order_id IS NOT NULL;

-- Gold: daily revenue per customer; its lag drives the whole chain
CREATE OR REPLACE DYNAMIC TABLE gold_daily_revenue
  TARGET_LAG = '15 minutes'
  WAREHOUSE = my_wh
AS
SELECT
  customer_id,
  DATE_TRUNC('day', order_ts) AS order_day,
  SUM(amount)                 AS revenue,
  COUNT(*)                    AS orders
FROM silver_orders
GROUP BY customer_id, DATE_TRUNC('day', order_ts);

-- Inspect refreshes
SELECT name, state, refresh_action, refresh_trigger, data_timestamp
FROM TABLE(INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY())
ORDER BY data_timestamp DESC
LIMIT 20;

-- Pause / resume and manual refresh
ALTER DYNAMIC TABLE gold_daily_revenue SUSPEND;
ALTER DYNAMIC TABLE gold_daily_revenue RESUME;
ALTER DYNAMIC TABLE gold_daily_revenue REFRESH;
```

## Notes
- Minimum `TARGET_LAG` is 1 minute. If no table downstream of a `DOWNSTREAM` table has a time-based lag, it never refreshes automatically.
- `REFRESH_MODE = INCREMENTAL` fails at creation if the query can't be refreshed incrementally; the default `AUTO` chooses for you, but check the chosen mode with `SHOW DYNAMIC TABLES`.
- Change tracking is enabled automatically on base tables, which requires the creating role to own them or have it already enabled.
- Each refresh uses the warehouse; longer lags mean fewer refreshes and lower cost.

## References
- [Dynamic tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-about)
- [CREATE DYNAMIC TABLE](https://docs.snowflake.com/en/sql-reference/sql/create-dynamic-table)
- [DYNAMIC_TABLE_REFRESH_HISTORY](https://docs.snowflake.com/en/sql-reference/functions/dynamic_table_refresh_history)
