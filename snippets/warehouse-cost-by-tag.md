# Attribute warehouse credits by warehouse, query tag and object tag

topics: cost-attribution, account-usage, tagging
tags: finops, credits, chargeback
level: advanced

Show total metered credits per warehouse, then split query compute by QUERY_TAG and by a `cost_center` object tag on users. This lets you charge teams for warehouses they share.

```sql
USE ROLE my_finops_role;   -- needs USAGE_VIEWER / GOVERNANCE_VIEWER on SNOWFLAKE, or IMPORTED PRIVILEGES
USE WAREHOUSE my_wh;

-- 1. Metered credits per warehouse, last 30 days (includes idle time)
SELECT warehouse_name,
       SUM(credits_used_compute)        AS compute_credits,
       SUM(credits_used_cloud_services) AS cloud_services_credits,
       SUM(credits_used)                AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY warehouse_name
ORDER BY total_credits DESC;

-- 2. Attributed query credits by QUERY_TAG (set with ALTER SESSION SET QUERY_TAG = '...')
SELECT COALESCE(NULLIF(query_tag, ''), '(untagged)')                        AS query_tag,
       SUM(credits_attributed_compute)                                      AS compute_credits,
       SUM(COALESCE(credits_used_query_acceleration, 0))                    AS qas_credits,
       COUNT(*)                                                             AS queries
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY compute_credits DESC;

-- 3. Attributed credits by a cost_center tag applied to USERS
--    (CREATE TAG my_db.tags.cost_center; ALTER USER jsmith SET TAG my_db.tags.cost_center = 'marketing';)
SELECT COALESCE(t.tag_value, '(no cost_center)') AS cost_center,
       SUM(q.credits_attributed_compute)          AS compute_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY q
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
       ON t.domain = 'USER'
      AND t.object_name = q.user_name
      AND t.tag_name = 'COST_CENTER'
WHERE q.start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY compute_credits DESC;

-- 4. Credits per warehouse tagged with cost_center (whole warehouse belongs to one team)
SELECT t.tag_value          AS cost_center,
       m.warehouse_name,
       SUM(m.credits_used)  AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY m
JOIN SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
  ON t.domain = 'WAREHOUSE'
 AND t.object_name = m.warehouse_name
 AND t.tag_name = 'COST_CENTER'
WHERE m.start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY total_credits DESC;

-- 5. Idle credits = metered compute minus attributed compute, per warehouse
WITH metered AS (
  SELECT warehouse_name, SUM(credits_used_compute) AS metered
  FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
  WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  GROUP BY 1
), attributed AS (
  SELECT warehouse_name, SUM(credits_attributed_compute) AS attributed
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
  WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  GROUP BY 1
)
SELECT m.warehouse_name, m.metered, a.attributed,
       m.metered - COALESCE(a.attributed, 0) AS idle_credits
FROM metered m LEFT JOIN attributed a USING (warehouse_name)
ORDER BY idle_credits DESC;
```

## Notes
- QUERY_ATTRIBUTION_HISTORY excludes idle time, cloud services, serverless features, and queries shorter than about 100 ms. It can lag up to 8 hours; WAREHOUSE_METERING_HISTORY can lag up to 3 hours.
- TAG_REFERENCES lists only directly assigned tags. It does not include tags inherited from a database or schema.
- Query tags are free text that users set themselves. Enforce a naming convention, or set a default with `ALTER USER ... SET QUERY_TAG`.
- Adaptive warehouses do not appear in QUERY_ATTRIBUTION_HISTORY; use QUERY_METERING_HISTORY for them.

## References
- [Attributing cost](https://docs.snowflake.com/en/user-guide/cost-attributing)
- [QUERY_ATTRIBUTION_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/query_attribution_history)
- [WAREHOUSE_METERING_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_metering_history)
