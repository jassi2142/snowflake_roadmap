# ACCOUNT_USAGE Views

The `SNOWFLAKE.ACCOUNT_USAGE` schema is the account's built-in history and metadata store. It holds a year of query, login, warehouse, storage and cost data plus metadata for current and dropped objects, which makes it the foundation for monitoring, cost analysis, security auditing and performance tuning.

## How it works

`ACCOUNT_USAGE` lives in the shared, Snowflake-provided `SNOWFLAKE` database. Its views fall into two types:

- **Object views** describe objects such as `TABLES`, `COLUMNS`, `USERS`, `ROLES`, `GRANTS_TO_ROLES` and `TABLE_STORAGE_METRICS`. They include **dropped objects**, often with a `DELETED` column and internal ID columns to tell apart objects recreated with the same name.
- **Historical views** record activity, such as `QUERY_HISTORY`, `LOGIN_HISTORY`, `WAREHOUSE_METERING_HISTORY`, `METERING_DAILY_HISTORY`, `STORAGE_USAGE` and `ACCESS_HISTORY`. Historical data is retained for **1 year**.

Compared with INFORMATION_SCHEMA, Account Usage:

- includes dropped objects;
- retains history for 1 year (INFORMATION_SCHEMA ranges from 7 days to 6 months);
- has **latency**, typically up to 2 hours and varying between about 45 minutes and 3 hours by view, with some views longer. For example, `QUERY_HISTORY` is about 45 minutes, `WAREHOUSE_METERING_HISTORY` about 3 hours, and `QUERY_ATTRIBUTION_HISTORY` up to 8 hours.

Some views require **Enterprise Edition**, for example `ACCESS_HISTORY` and `MATERIALIZED_VIEW_REFRESH_HISTORY`.

**Access.** By default only ACCOUNTADMIN can query these views. You can grant access in two ways:

- `GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE ...` gives access to all schemas.
- **SNOWFLAKE database roles** give finer control: `OBJECT_VIEWER` (object metadata), `USAGE_VIEWER` (historical usage and cost), `GOVERNANCE_VIEWER` (governance data, including QUERY_HISTORY and ACCESS_HISTORY) and `SECURITY_VIEWER` (security data such as LOGIN_HISTORY and grants). Snowflake recommends database roles to avoid unintentionally granting broader access.

## Example

Grant a monitoring role access to usage and cost views only:

```sql
USE ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE monitoring_role;
```

Credits by warehouse for the last 30 days:

```sql
SELECT warehouse_name,
       SUM(credits_used) AS credits
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY warehouse_name
ORDER BY credits DESC;
```

Failed logins by user this month:

```sql
SELECT user_name,
       COUNT_IF(is_success = 'NO') AS failed_logins,
       COUNT(*)                    AS total_logins
FROM snowflake.account_usage.login_history
WHERE event_timestamp >= DATE_TRUNC('month', CURRENT_DATE())
GROUP BY user_name
ORDER BY failed_logins DESC;
```

Longest-running queries yesterday:

```sql
SELECT query_id, user_name, warehouse_name, total_elapsed_time / 1000 AS seconds
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD('day', -1, CURRENT_DATE())
  AND start_time < CURRENT_DATE()
ORDER BY total_elapsed_time DESC
LIMIT 10;
```

## Best practices

- Always filter historical views on their time column (`start_time`, `event_timestamp`, `usage_date`) to keep queries fast.
- Select only the columns you need; Snowflake notes these views can change, so avoid `SELECT *` in production code.
- Use SNOWFLAKE database roles for least-privilege access.
- Account for latency in alerts and dashboards; use INFORMATION_SCHEMA when you need data from the last few minutes.
- To reconcile cost views with ORGANIZATION_USAGE, set the session time zone to UTC first.
- Copy data you need beyond one year into your own tables on a schedule.

## Common pitfalls

- Expecting a query that ran a minute ago to appear immediately.
- Forgetting that dropped objects are included, which can double-count tables in inventory reports unless you filter on `deleted IS NULL`.
- Granting IMPORTED PRIVILEGES broadly when a narrower database role would do.
- Treating `credits_used` in most views as billed credits; cloud services adjustments are only reflected in `METERING_DAILY_HISTORY`.

## Learn more

- [Account Usage](https://docs.snowflake.com/en/sql-reference/account-usage)
- [Exploring compute cost](https://docs.snowflake.com/en/user-guide/cost-exploring-compute)

## Knowledge check

### An operations team needs to see a query that finished 2 minutes ago. Why might ACCOUNT_USAGE.QUERY_HISTORY not show it yet?
- [ ] The view only includes failed queries
- [x] Account Usage views have latency; QUERY_HISTORY can lag by up to about 45 minutes
- [ ] The view only keeps 7 days of history
- [ ] The query must be tagged first
> Account Usage data is extracted from internal metadata with a delay, so very recent activity is better found with INFORMATION_SCHEMA table functions.

### You want an analyst role to read warehouse metering and storage usage, but not login history or grants. What is the best approach?
- [ ] Grant ACCOUNTADMIN to the role
- [ ] Grant IMPORTED PRIVILEGES on the SNOWFLAKE database
- [x] Grant the SNOWFLAKE.USAGE_VIEWER database role
- [ ] Grant SECURITY_VIEWER
> USAGE_VIEWER covers historical usage views such as metering and storage, while security views like LOGIN_HISTORY are under SECURITY_VIEWER.

### A report needs a list of tables that were dropped in the last 6 months. Which source is appropriate?
- [ ] INFORMATION_SCHEMA.TABLES
- [x] ACCOUNT_USAGE.TABLES, filtering on the DELETED column
- [ ] SHOW TABLES without HISTORY
- [ ] QUERY_HISTORY
> Account Usage object views include dropped objects with a DELETED timestamp, while INFORMATION_SCHEMA shows only current objects.
