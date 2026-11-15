# Caching Layers

Snowflake uses several caches so that repeated work does not have to be redone. Understanding which cache serves a query, and what invalidates it, explains why the same query can take ten seconds once and milliseconds the next time, and helps you tune warehouses for both speed and cost.

## How it works

There are three layers to know:

**1. Result cache (persisted query results).** Lives in the cloud services layer and is shared across warehouses. If a query is repeated and nothing relevant has changed, Snowflake returns the stored result without running the query, so no warehouse compute is needed. Documented behavior:

- Results are kept for **24 hours**. Each reuse resets the 24-hour period, up to a maximum of **31 days** from the first execution.
- The new query must match the previous one exactly; differences such as an added table alias or different keyword casing prevent reuse.
- The query must not use non-reusable functions (for example RANDOM, UUID_STRING), external functions, or hybrid tables.
- The underlying table data and micro-partitions must not have changed (including reclustering).
- The role must have the required privileges on the tables.
- Result reuse is controlled by the `USE_CACHED_RESULT` parameter (on by default) at account, user or session level.

**2. Warehouse cache (local disk cache).** A running warehouse keeps table data it has read on local storage. Later queries on the same warehouse can read from this cache instead of remote storage. The cache is **dropped when the warehouse suspends**, and different warehouses do not share it. The Query Profile and QUERY_HISTORY report `percentage_scanned_from_cache`.

**3. Metadata.** The cloud services layer keeps micro-partition metadata such as row counts and min/max values. Some queries, for example `COUNT(*)` on a table or `MIN`/`MAX` on a column, can often be answered from metadata without scanning data.

The auto-suspend setting is the main trade-off for the warehouse cache. Snowflake's guidance: immediate suspension for tasks, about 5 minutes for DevOps, DataOps and data science, and at least 10 minutes for BI and SELECT-heavy warehouses. A running warehouse consumes credits even when idle, so a long auto-suspend only makes sense if queries actually arrive often enough to reuse the cache.

## Example

Check the cache hit rate for each warehouse over the last month:

```sql
SELECT warehouse_name,
       COUNT(*) AS query_count,
       SUM(bytes_scanned * percentage_scanned_from_cache) / NULLIF(SUM(bytes_scanned), 0)
         AS pct_scanned_from_cache
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD('month', -1, CURRENT_TIMESTAMP())
  AND bytes_scanned > 0
GROUP BY warehouse_name
ORDER BY pct_scanned_from_cache;
```

Disable the result cache for a benchmarking session so timings reflect real execution:

```sql
ALTER SESSION SET USE_CACHED_RESULT = FALSE;
```

Set a 10-minute auto-suspend (the value is in seconds) for a BI warehouse:

```sql
ALTER WAREHOUSE bi_wh SET AUTO_SUSPEND = 600;
```

Reuse a previous result for further processing with RESULT_SCAN:

```sql
SHOW TABLES IN SCHEMA sales.public;
SELECT "name", "rows" FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) WHERE "rows" = 0;
```

## Best practices

- Route similar, repeated workloads (such as one BI tool) to the same warehouse to improve warehouse cache hits.
- Have BI tools generate identical SQL text for identical requests so the result cache can be used.
- Match auto-suspend to the gap between queries; do not keep a warehouse running if queries arrive every 30 minutes.
- Turn off `USE_CACHED_RESULT` when benchmarking, and run tests more than once to separate cold and warm warehouse cache effects.

## Common pitfalls

- Assuming the result cache works across a query that uses CURRENT_TIMESTAMP or RANDOM.
- Expecting the warehouse cache to survive a suspend or be shared between warehouses.
- Setting very short auto-suspend on a BI warehouse, causing constant cold starts and the 60-second minimum charge on each resume.
- Benchmarking a query once, seeing a millisecond result-cache response, and concluding the query is fast.

## Learn more

- [Using Persisted Query Results](https://docs.snowflake.com/en/user-guide/querying-persisted-results)
- [Optimizing the warehouse cache](https://docs.snowflake.com/en/user-guide/performance-query-warehouse-cache)

## Knowledge check

### A dashboard query is re-run every hour on an unchanged table and returns instantly without using warehouse credits. Which cache is serving it?
- [ ] Warehouse local disk cache
- [x] Result cache (persisted query results)
- [ ] Metadata cache only
- [ ] The materialized view cache
> The result cache returns stored results for identical queries on unchanged data without running the query on a warehouse.

### Two analysts run the same query on different warehouses. The second one is not faster. Why?
- [ ] The result cache is per user
- [x] The result cache should apply, but if it was not used, the warehouse cache cannot help because it is not shared between warehouses
- [ ] Warehouse caches are always cleared after each query
- [ ] Metadata is stored per warehouse
> Each warehouse has its own local cache, so data cached on one warehouse is not available to another; only the result cache is shared, and it requires an exact match and unchanged data.

### A BI warehouse receives queries every 2 minutes during business hours and has AUTO_SUSPEND = 60. What change most likely improves performance?
- [ ] Reduce AUTO_SUSPEND to 0
- [x] Increase AUTO_SUSPEND to around 10 minutes so the warehouse cache is preserved
- [ ] Disable USE_CACHED_RESULT
- [ ] Switch to a larger warehouse size
> Frequent suspensions drop the warehouse cache; Snowflake recommends at least 10 minutes for BI warehouses so repeated reads can use cached data.
