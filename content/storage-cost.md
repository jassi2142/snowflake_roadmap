# Storage Cost Optimization

Storage is billed per terabyte per month on the average bytes stored each day, and for mature accounts it often grows silently: Time Travel and Fail-safe copies of churned data, clones that pin old micro-partitions, staged files, and tables nobody queries. Optimizing storage is mostly about understanding *which state* bytes are in and choosing retention and table types deliberately.

## How it works

**Byte states.** `TABLE_STORAGE_METRICS` breaks each table's billed bytes into:

- `ACTIVE_BYTES` – queryable data.
- `TIME_TRAVEL_BYTES` – changed or deleted data still within the retention period.
- `FAILSAFE_BYTES` – data past Time Travel but within Fail-safe.
- `RETAINED_FOR_CLONE_BYTES` – deleted data no longer in Time Travel or Fail-safe but still referenced by clones (or WORM backups).

Bytes are **owned by the table where they were first added**. A clone shares micro-partitions with its source until either side changes; each change makes the modifying table own the new bytes. If you delete data from a source table that a clone still references, the source keeps paying for those bytes as `RETAINED_FOR_CLONE_BYTES`. `CLONE_GROUP_ID` identifies the oldest ancestor, so you can analyze clone families. Each `CREATE OR REPLACE TABLE` creates a new version, and dropped versions keep accruing Time Travel and Fail-safe storage.

The Account Usage view includes dropped tables and has up to 90 minutes of latency. The INFORMATION_SCHEMA version returns rows only for ACCOUNTADMIN.

**Retention levers.**

| Table type | Time Travel | Fail-safe |
| --- | --- | --- |
| Permanent | 0-1 day (Standard); 0-90 days (Enterprise+) | 7 days |
| Transient | 0 or 1 day | None |
| Temporary | 0 or 1 day, ends with the session | None |

Time Travel defaults to 1 day. `DATA_RETENTION_TIME_IN_DAYS` can be set at account, database, schema and table level and is inherited downward. `MIN_DATA_RETENTION_TIME_IN_DAYS` at the account level enforces a floor. Decreasing retention moves out-of-window data to Fail-safe via a background process. Historical data is kept as the changed portion, except that full copies are kept when tables are dropped or truncated.

**Trade-offs for architects.**

- **Transient for reproducible data.** Staging, ETL work tables and derived layers that can be rebuilt from source avoid all Fail-safe cost. The price is losing Snowflake-side recovery after Time Travel ends; long-lived source-of-truth tables should stay permanent.
- **Churn multiplies history.** High-churn tables (frequent MERGE or full reloads) generate large Time Travel and Fail-safe volumes; with 90-day retention they can cost several times their active size. Match retention to the real recovery requirement per layer.
- **Reclustering and rewrites churn too.** Clustering and large UPDATEs rewrite micro-partitions, creating history bytes.
- **Clones are cheap until they diverge.** Long-lived dev clones of churning production tables steadily accumulate retained bytes.

## Example

Find tables where historical bytes dominate:

```sql
SELECT table_catalog, table_schema, table_name, is_transient,
       active_bytes             / POWER(1024, 4) AS active_tb,
       time_travel_bytes        / POWER(1024, 4) AS tt_tb,
       failsafe_bytes           / POWER(1024, 4) AS fs_tb,
       retained_for_clone_bytes / POWER(1024, 4) AS clone_tb
FROM snowflake.account_usage.table_storage_metrics
WHERE (time_travel_bytes + failsafe_bytes + retained_for_clone_bytes) > active_bytes
ORDER BY (time_travel_bytes + failsafe_bytes + retained_for_clone_bytes) DESC
LIMIT 50;
```

Find large tables not read in 90 days (`ACCESS_HISTORY` requires Enterprise Edition):

```sql
WITH accessed AS (
  SELECT DISTINCT f.value:"objectName"::STRING AS full_name
  FROM snowflake.account_usage.access_history ah,
       LATERAL FLATTEN(input => ah.base_objects_accessed) f
  WHERE ah.query_start_time >= DATEADD('day', -90, CURRENT_TIMESTAMP())
)
SELECT t.table_catalog || '.' || t.table_schema || '.' || t.table_name AS full_name,
       t.active_bytes / POWER(1024, 3) AS active_gb
FROM snowflake.account_usage.table_storage_metrics t
LEFT JOIN accessed a
  ON a.full_name = t.table_catalog || '.' || t.table_schema || '.' || t.table_name
WHERE t.deleted = FALSE
  AND a.full_name IS NULL
ORDER BY t.active_bytes DESC
LIMIT 50;
```

Apply retention by layer and create reproducible tables as transient:

```sql
ALTER SCHEMA analytics.staging SET DATA_RETENTION_TIME_IN_DAYS = 1;
CREATE TRANSIENT TABLE analytics.staging.orders_work LIKE analytics.raw.orders;
```

## Best practices

- Set retention per schema layer (raw, staging, curated) from documented recovery objectives rather than a single account-wide value.
- Use transient databases or schemas for reproducible pipeline layers.
- Expire dev and test clones on a schedule; treat clone lifetime as a cost decision.
- Prefer incremental MERGE patterns over full `CREATE OR REPLACE` reloads of large tables when history volume matters.
- Review staged files and remove loaded files with `PURGE = TRUE` or `REMOVE`.
- Review unused large tables with owners before dropping, and remember that dropping only starts the Time Travel and Fail-safe clock.

## Common pitfalls

- Setting retention to 0 at the account level, which removes recovery for everything.
- Expecting `DROP TABLE` to cut storage immediately; data remains in Time Travel then Fail-safe (permanent tables) for up to 97 days.
- Dropping a schema expecting child tables' shorter retention to apply; when a container is dropped, child objects use the container's retention.
- Converting a permanent table to transient in place; there is no ALTER for this, you must recreate it (for example with CTAS) and reapply grants.
- Overlooking `RETAINED_FOR_CLONE_BYTES` charged to the source table after deleting data that a clone still references.

## Learn more

- [TABLE_STORAGE_METRICS view](https://docs.snowflake.com/en/sql-reference/account-usage/table_storage_metrics)
- [Storage costs for Time Travel and Fail-safe](https://docs.snowflake.com/en/user-guide/data-cdp-storage-costs)
- [Understanding & using Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel)

## Knowledge check

### A 2 TB permanent staging table is fully reloaded every day with CREATE OR REPLACE, with 30-day retention. Storage metrics show tens of terabytes of history. What is the best redesign?
- [ ] Increase retention to 90 days to smooth the cost
- [x] Make the table transient with 0 or 1 day retention, since it can be rebuilt from source
- [ ] Add a clustering key
- [ ] Clone the table daily before reloading
> Each replace creates a new version whose old data stays in Time Travel and then Fail-safe; a transient table with minimal retention removes Fail-safe and most history cost for reproducible data.

### A source table shows large RETAINED_FOR_CLONE_BYTES after old rows were deleted. What does this mean?
- [ ] The clone is being charged for the deleted rows
- [x] The deleted micro-partitions are still referenced by a clone, so they are retained and billed to the source table that originally owned them
- [ ] The rows are still in Time Travel
- [ ] Fail-safe has been extended
> Bytes are billed to the table that first added them; once outside Time Travel and Fail-safe, they remain as retained-for-clone bytes while a clone references them.

### You reduce a schema's retention from 90 days to 7 days. Which statement is correct?
- [ ] All historical data is deleted immediately
- [ ] Tables already dropped from the schema now keep only 7 days
- [x] Data outside the new window in active tables moves to Fail-safe via a background process, while previously dropped tables keep their original retention
- [ ] Fail-safe is reduced to 0 days
> Decreasing retention moves out-of-window history to Fail-safe asynchronously, and changes to a container do not affect objects that were already dropped.
