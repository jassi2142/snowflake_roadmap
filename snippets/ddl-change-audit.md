# Audit DDL changes (who changed what, and when)

topics: access-history, account-usage, schema-change
tags: governance, audit, security
level: advanced

Get a log of CREATE, ALTER, DROP and policy or tag changes for an incident review or a change-control check. The `object_modified_by_ddl` column in ACCESS_HISTORY records which object changed and how, and joining to QUERY_HISTORY adds the role, the statement type and the SQL text.

```sql
USE ROLE governance_viewer;   -- a role that can read SNOWFLAKE.ACCOUNT_USAGE
USE WAREHOUSE my_wh;

-- 1. Structured DDL log for the last 7 days
SELECT
  ah.query_start_time,
  ah.user_name,
  qh.role_name,
  ah.object_modified_by_ddl:"operationType"::STRING AS operation,     -- CREATE, ALTER, DROP, REPLACE, UNDROP, ...
  ah.object_modified_by_ddl:"objectDomain"::STRING  AS object_type,
  ah.object_modified_by_ddl:"objectName"::STRING    AS object_name,
  ah.object_modified_by_ddl:"properties"            AS changed_properties,  -- columns, policies, tags, comments...
  qh.query_type,
  LEFT(qh.query_text, 500)                          AS query_text
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh
  ON  qh.query_id = ah.query_id
  AND qh.start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())   -- bound both sides of the join
WHERE ah.query_start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
  AND ah.object_modified_by_ddl IS NOT NULL
ORDER BY ah.query_start_time DESC;

-- 2. Focus on destructive or protection-weakening changes in production
SELECT
  ah.query_start_time,
  ah.user_name,
  ah.object_modified_by_ddl:"operationType"::STRING AS operation,
  ah.object_modified_by_ddl:"objectName"::STRING    AS object_name
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah
WHERE ah.query_start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND ah.object_modified_by_ddl:"objectName"::STRING ILIKE 'PROD_DB.%'
  AND (ah.object_modified_by_ddl:"operationType"::STRING IN ('DROP', 'REPLACE')
       OR ah.object_modified_by_ddl:"properties"::STRING ILIKE '%policy%')
ORDER BY ah.query_start_time DESC;

-- 3. Fallback with QUERY_HISTORY only: also catches DDL on objects outside
--    ACCESS_HISTORY's DDL scope (e.g. warehouses, users, roles), but you parse the SQL text yourself
SELECT start_time, user_name, role_name, query_type, execution_status,
       LEFT(query_text, 500) AS query_text
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
  AND (query_type LIKE 'CREATE%' OR query_type LIKE 'ALTER%' OR query_type LIKE 'DROP%'
       OR query_type IN ('GRANT', 'REVOKE'))
ORDER BY start_time DESC;
```

## Notes
- ACCESS_HISTORY requires Enterprise Edition or higher and has up to about 3 hours of latency. QUERY_HISTORY is available in all editions and keeps 365 days.
- `object_modified_by_ddl` covers DDL on databases, schemas, tables, views and columns, including setting row access and masking policies and tag changes. With `IF [NOT] EXISTS`, only CREATE or REPLACE is recorded.
- Failed statements appear in QUERY_HISTORY, with `execution_status = 'FAIL'`, but not in ACCESS_HISTORY.
- To alert on changes as they happen, put query 2 in an alert with a short lookback window, remembering the view's latency.

## References
- [ACCESS_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/access_history)
- [QUERY_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/query_history)
- [Access History](https://docs.snowflake.com/en/user-guide/access-history)
