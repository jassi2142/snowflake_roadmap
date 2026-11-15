# INFORMATION_SCHEMA

Every Snowflake database contains an `INFORMATION_SCHEMA` schema with views and table functions that describe the objects in that database and recent account activity. It is real-time, needs no special grants beyond normal object privileges, and is the right tool when you need current metadata or activity from the last few minutes.

## How it works

`INFORMATION_SCHEMA` is created automatically in each database and is read-only. It has two kinds of objects:

**Views** describe objects in that database, such as `TABLES`, `COLUMNS`, `VIEWS`, `SCHEMATA`, `TABLE_STORAGE_METRICS`, `FUNCTIONS` and `PROCEDURES`. Results are filtered to objects your current role has privileges on.

**Table functions** return historical and usage data, such as `QUERY_HISTORY` (with `QUERY_HISTORY_BY_SESSION`, `_BY_USER` and `_BY_WAREHOUSE` variants), `TASK_HISTORY`, `ALERT_HISTORY`, `COPY_HISTORY`, `WAREHOUSE_METERING_HISTORY` and `MATERIALIZED_VIEW_REFRESH_HISTORY`. Table functions must be called with `TABLE(...)` in the FROM clause, and the session must be using an INFORMATION_SCHEMA or the function name must be fully qualified.

How it compares with `SNOWFLAKE.ACCOUNT_USAGE`:

| Aspect | INFORMATION_SCHEMA | ACCOUNT_USAGE |
| --- | --- | --- |
| Latency | None | About 45 minutes to 3 hours, varying by view |
| History retention | 7 days to 6 months, varying by view or function | 1 year |
| Dropped objects | Not included | Included |
| Scope | One database (views); account activity visible to your role (functions) | Whole account |

Specific limits for the `QUERY_HISTORY` table functions:

- The time range must be within the **last 7 days**.
- `RESULT_LIMIT` defaults to **100** and can be set from **1 to 10,000**.
- The time range and RESULT_LIMIT are applied **before** your WHERE clause, so a filter only sees the most recent rows returned by the function. Increase RESULT_LIMIT when filtering.
- You see your own queries, plus others' queries on warehouses where your role has MONITOR or OPERATE.

`TABLE_STORAGE_METRICS` in INFORMATION_SCHEMA returns rows only for the ACCOUNTADMIN role.

## Example

List the largest tables in a database:

```sql
SELECT table_schema, table_name, row_count, bytes / POWER(1024, 3) AS gb
FROM sales_db.information_schema.tables
WHERE table_type = 'BASE TABLE'
ORDER BY bytes DESC NULLS LAST
LIMIT 20;
```

Find columns whose name suggests personal data:

```sql
SELECT table_schema, table_name, column_name, data_type
FROM sales_db.information_schema.columns
WHERE column_name ILIKE ANY ('%email%', '%phone%', '%ssn%');
```

Show the last hour of queries on a warehouse, raising the result limit before filtering:

```sql
SELECT query_id, user_name, execution_status, total_elapsed_time / 1000 AS seconds
FROM TABLE(sales_db.information_schema.query_history_by_warehouse(
       WAREHOUSE_NAME => 'BI_WH',
       END_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
       RESULT_LIMIT => 10000))
WHERE execution_status = 'FAILED_WITH_ERROR'
ORDER BY start_time DESC;
```

## Best practices

- Use INFORMATION_SCHEMA for near-real-time checks (for example, "did my task just fail?") and ACCOUNT_USAGE for trends and audits.
- Qualify views with the database name so the query does not depend on the current database.
- Pass time range arguments to table functions instead of relying only on WHERE filters.
- Raise RESULT_LIMIT when you need to filter a busy period.
- Remember results depend on the current role; switch roles if objects seem to be missing.

## Common pitfalls

- Using QUERY_HISTORY table functions for month-long analysis; anything older than 7 days returns an error.
- Expecting dropped tables in INFORMATION_SCHEMA.TABLES.
- Writing a WHERE filter and getting few results because only the default 100 rows were fetched first.
- Looking for materialized views in INFORMATION_SCHEMA.VIEWS; they appear in INFORMATION_SCHEMA.TABLES instead.
- Querying INFORMATION_SCHEMA views across many databases in a loop when one ACCOUNT_USAGE query would do.

## Learn more

- [QUERY_HISTORY table functions](https://docs.snowflake.com/en/sql-reference/functions/query_history)
- [Account Usage (differences from Information Schema)](https://docs.snowflake.com/en/sql-reference/account-usage)

## Knowledge check

### A task failed 3 minutes ago and you need the error immediately. Which source is best?
- [ ] ACCOUNT_USAGE.TASK_HISTORY
- [x] The INFORMATION_SCHEMA TASK_HISTORY table function
- [ ] ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
- [ ] ORGANIZATION_USAGE
> INFORMATION_SCHEMA table functions have no latency, while Account Usage views can lag by tens of minutes or more.

### You query INFORMATION_SCHEMA.QUERY_HISTORY() with WHERE user_name = 'BOB' on a busy account and get only two rows, although Bob ran dozens of queries today. What is the likely cause?
- [ ] Bob's queries were all served from the result cache
- [x] RESULT_LIMIT defaulted to 100, and the WHERE clause was applied only to those 100 most recent rows
- [ ] INFORMATION_SCHEMA only stores one hour of history
- [ ] The function only returns failed queries
> The function applies its time range and RESULT_LIMIT before the WHERE clause; raising RESULT_LIMIT (up to 10,000) or using QUERY_HISTORY_BY_USER fixes this.

### Which requirement can INFORMATION_SCHEMA not satisfy?
- [ ] Listing current tables in a database
- [ ] Finding columns of a given data type
- [x] Reporting query history from 3 months ago
- [ ] Viewing queries from the last hour
> QUERY_HISTORY table functions cover only the last 7 days; longer history requires ACCOUNT_USAGE.
