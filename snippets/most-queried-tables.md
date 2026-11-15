# Most-queried tables in the last 30 days (ACCESS_HISTORY)

topics: access-history, account-usage
tags: governance, monitoring, lineage, cost
level: advanced

Find the tables your account reads most, how many distinct users read them, and which tables nobody has touched. The results help you decide where to spend tuning effort (clustering, search optimization) and which tables are candidates for archiving.

```sql
USE ROLE governance_viewer;   -- a role that can read SNOWFLAKE.ACCOUNT_USAGE (IMPORTED PRIVILEGES or a SNOWFLAKE database role)
USE WAREHOUSE my_wh;

-- 1. Top tables by query count. base_objects_accessed resolves views to the tables underneath them.
SELECT
  obj.value:"objectName"::STRING          AS table_name,
  COUNT(DISTINCT ah.query_id)             AS query_count,
  COUNT(DISTINCT ah.user_name)            AS distinct_users,
  MAX(ah.query_start_time)                AS last_accessed
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
     LATERAL FLATTEN(input => ah.base_objects_accessed) obj
WHERE ah.query_start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND UPPER(obj.value:"objectDomain"::STRING) = 'TABLE'
GROUP BY table_name
ORDER BY query_count DESC
LIMIT 25;

-- 2. Same idea for the objects users name directly (views appear as views)
SELECT
  obj.value:"objectDomain"::STRING AS object_type,
  obj.value:"objectName"::STRING   AS object_name,
  COUNT(DISTINCT ah.query_id)      AS query_count
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
     LATERAL FLATTEN(input => ah.direct_objects_accessed) obj
WHERE ah.query_start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND UPPER(obj.value:"objectDomain"::STRING) IN ('TABLE', 'VIEW', 'MATERIALIZED VIEW')
GROUP BY object_type, object_name
ORDER BY query_count DESC
LIMIT 25;

-- 3. Tables with no reads in 30 days, largest first: candidates for review
WITH read_tables AS (
  SELECT DISTINCT obj.value:"objectId"::NUMBER AS table_id
  FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
       LATERAL FLATTEN(input => ah.base_objects_accessed) obj
  WHERE ah.query_start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
)
SELECT t.table_catalog, t.table_schema, t.table_name,
       t.row_count, ROUND(t.bytes / POWER(1024, 3), 2) AS size_gb, t.last_altered
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
LEFT JOIN read_tables r ON r.table_id = t.table_id
WHERE t.deleted IS NULL
  AND t.table_type = 'BASE TABLE'
  AND t.created < DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND r.table_id IS NULL
ORDER BY t.bytes DESC NULLS LAST
LIMIT 50;
```

## Notes
- ACCESS_HISTORY requires Enterprise Edition or higher. ACCOUNT_USAGE views have some latency (up to about 3 hours for ACCESS_HISTORY) and keep 365 days of history.
- Always filter on `query_start_time`. The view is large, and a 30-day window keeps the scan manageable.
- A table being unread doesn't mean it's safe to drop. Tasks, shares and quarterly jobs may still need it. Check lineage and owners first.
- Not recorded: RESULT_SCAN reuse, Snowflake-provided table functions, ACCOUNT_USAGE views, and failed queries.

## References
- [ACCESS_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/access_history)
- [Access History](https://docs.snowflake.com/en/user-guide/access-history)
- [TABLES view](https://docs.snowflake.com/en/sql-reference/account-usage/tables)
