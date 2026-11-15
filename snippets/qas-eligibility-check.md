# Find QAS candidates and enable Query Acceleration

topics: qas, query-history-analysis, warehouse-basics
tags: performance, qas, warehouses
level: advanced

The Query Acceleration Service (QAS) helps large scans and outlier queries by borrowing serverless compute. Before you turn it on, find the warehouses with the most eligible time and estimate the speedup for a specific query.

```sql
USE ROLE my_admin_role;   -- ACCOUNT_USAGE access + MODIFY on the warehouse
USE WAREHOUSE my_wh;

-- 1. Warehouses with the most QAS-eligible time over the last 7 days
SELECT warehouse_name,
       COUNT(*)                              AS eligible_queries,
       SUM(eligible_query_acceleration_time) AS eligible_seconds,
       MAX(upper_limit_scale_factor)         AS max_useful_scale_factor
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name
ORDER BY eligible_seconds DESC;

-- 2. Top individual queries where most of the runtime is eligible
SELECT query_id,
       warehouse_name,
       warehouse_size,
       DATEDIFF(second, start_time, end_time)  AS duration_s,
       eligible_query_acceleration_time        AS eligible_s,
       upper_limit_scale_factor,
       LEFT(query_text, 120)                   AS query_preview
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY eligible_query_acceleration_time DESC
LIMIT 20;

-- 3. Estimate run time at different scale factors for one query (last 14 days)
SELECT PARSE_JSON(SYSTEM$ESTIMATE_QUERY_ACCELERATION('01bxxxxx-0000-0000-0000-000000000000')) AS estimate;
-- Returns status, originalQueryTime, eligible, upperLimitScaleFactor and estimatedQueryTimes per scale factor

-- 4. Enable QAS on the chosen warehouse with a cost cap
ALTER WAREHOUSE my_reporting_wh SET
  ENABLE_QUERY_ACCELERATION = TRUE
  QUERY_ACCELERATION_MAX_SCALE_FACTOR = 4;   -- 0 = no cap; default 8

-- 5. Afterwards: QAS credits per warehouse
SELECT warehouse_name,
       DATE_TRUNC('day', start_time) AS usage_day,
       SUM(credits_used)             AS qas_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY
WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name, usage_day
ORDER BY usage_day, warehouse_name;
```

## Notes
- Eligible statements are SELECT, INSERT, CTAS and COPY INTO. Large scans with selective filters or aggregation benefit the most.
- QUERY_ACCELERATION_ELIGIBLE lists only queries that were not accelerated, so accelerated queries leave the view once QAS is on. The view can lag up to 3 hours.
- QAS is billed as serverless credits on top of the warehouse. The scale factor caps how much extra compute one query can use, as a multiple of the warehouse size.
- To turn QAS off: `ALTER WAREHOUSE my_reporting_wh SET ENABLE_QUERY_ACCELERATION = FALSE;`

## References
- [Using the Query Acceleration Service](https://docs.snowflake.com/en/user-guide/query-acceleration-service)
- [QUERY_ACCELERATION_ELIGIBLE view](https://docs.snowflake.com/en/sql-reference/account-usage/query_acceleration_eligible)
- [SYSTEM$ESTIMATE_QUERY_ACCELERATION](https://docs.snowflake.com/en/sql-reference/functions/system_estimate_query_acceleration)
