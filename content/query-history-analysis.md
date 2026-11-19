# Workload Analysis (finding expensive/slow queries with QUERY_HISTORY, query_parameterized_hash, QUERY_ATTRIBUTION_HISTORY)

Optimizing one slow query is tactics; workload analysis is strategy. By aggregating query history across thousands of executions you can find the query *patterns* that dominate elapsed time and credits, rank them by business impact, and verify that a fix actually moved the needle.

## How it works

Three Account Usage sources form the backbone of workload analysis:

- **`SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`** – one row per statement with timing (`total_elapsed_time`, `compilation_time`, `execution_time`, the `queued_*` columns), I/O (`bytes_scanned`, `partitions_scanned`, `partitions_total`, `bytes_spilled_to_local_storage`, `bytes_spilled_to_remote_storage`), context (`warehouse_name`, `warehouse_size`, `user_name`, `role_name`, `query_tag`) and `credits_used_cloud_services`. Latency is up to 45 minutes; retention is 1 year.
- **`query_hash` and `query_parameterized_hash`** – `query_hash` is computed on the canonicalized SQL text, so it ignores whitespace, comments and identifier case. `query_parameterized_hash` additionally parameterizes literals used in predicates with `=`, `!=`, `>=` or `<=`, so `WHERE name = 'TIM'` and `WHERE name = 'AIHUA'` share a hash. This is the right grouping key for dashboards and applications that issue the same query with different filter values. Both have companion `*_version` columns because the hashing logic can change; account for version changes when comparing long time ranges.
- **`SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY`** – per-query warehouse credits in `credits_attributed_compute` (plus `credits_used_query_acceleration`). Latency is up to 8 hours; retention is 1 year.

Understand what attribution includes and excludes before you present numbers:

- Credits are split among concurrent queries by a weighted average of resource consumption, including resizing and multi-cluster scaling.
- Warehouse **idle time is not attributed**, so the sum of query credits is lower than warehouse metering. Reconcile against `WAREHOUSE_METERING_HISTORY` and report idle as its own line.
- Very short queries (about 100 ms or less) are not included.
- Cloud services, storage, data transfer, serverless features and AI token costs are excluded.
- For stored procedures, sum child queries using `root_query_id`.

The design decision is the ranking metric. Elapsed time optimizes user experience; attributed credits optimizes spend. A five-second dashboard query run 200,000 times a month often outranks a single two-hour batch job on both.

In Snowsight under **Monitoring > Performance explorer**, Snowflake provides a built-in visual console that automatically aggregates query execution patterns using `query_parameterized_hash`. It flags slow query clusters, sudden execution time regressions, spilling trends, and warehouse queuing bottlenecks without requiring custom SQL scripts.

## Example

Top recurring patterns by attributed credits over the last 30 days:

```sql
SELECT query_parameterized_hash,
       COUNT(*)                         AS executions,
       SUM(credits_attributed_compute)  AS credits,
       AVG(DATEDIFF('millisecond', start_time, end_time)) AS avg_ms,
       ANY_VALUE(query_id)              AS sample_query_id,
       ANY_VALUE(warehouse_name)        AS sample_warehouse
FROM snowflake.account_usage.query_attribution_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY query_parameterized_hash
ORDER BY credits DESC
LIMIT 25;
```

Enrich the top patterns with diagnostic signals from QUERY_HISTORY:

```sql
SELECT query_parameterized_hash,
       COUNT(*)                                        AS executions,
       SUM(total_elapsed_time) / 1000 / 3600           AS total_hours,
       AVG(partitions_scanned / NULLIF(partitions_total, 0)) AS avg_scan_ratio,
       SUM(bytes_spilled_to_remote_storage)            AS remote_spill_bytes,
       SUM(queued_overload_time) / 1000                AS queued_overload_s,
       ANY_VALUE(LEFT(query_text, 200))                AS sample_text
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND execution_status = 'SUCCESS'
  AND warehouse_name IS NOT NULL
GROUP BY query_parameterized_hash
ORDER BY total_hours DESC
LIMIT 25;
```

A high scan ratio points to pruning problems, remote spill to undersized warehouses or bad joins, and high overload queuing to concurrency rather than query design.

## Best practices

- Group by `query_parameterized_hash` first; drill into individual `query_id`s only for the top patterns.
- Always bound queries on `start_time`; these views are large.
- Separate compilation, queuing and execution time; each has a different fix.
- Snapshot baseline metrics before a change, then compare the same hash afterwards.
- Use `query_tag` conventions so application workloads are attributable without parsing SQL text.

## Common pitfalls

- Presenting attributed credits as total warehouse cost while ignoring idle time.
- Using the INFORMATION_SCHEMA QUERY_HISTORY function for trend analysis; it covers only 7 days and returns at most 10,000 rows.
- Joining QUERY_HISTORY and QUERY_ATTRIBUTION_HISTORY on recent data without allowing for their different latencies (45 minutes vs. up to 8 hours).
- Comparing hashes across a hash version change and concluding that a query disappeared.

## Learn more

- [Using the query hash to identify patterns](https://docs.snowflake.com/en/user-guide/query-hash)
- [QUERY_ATTRIBUTION_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/query_attribution_history)
- [Account Usage](https://docs.snowflake.com/en/sql-reference/account-usage)

## Knowledge check

### A BI tool sends the same dashboard query with a different customer_id literal each time. Which column groups these executions together?
- [ ] query_id
- [ ] query_hash
- [x] query_parameterized_hash
- [ ] session_id
> query_parameterized_hash parameterizes predicate literals compared with =, !=, >= or <=, so executions differing only in those values share a hash; query_hash would differ.

### Finance notes that the sum of credits_attributed_compute for a warehouse is 30% lower than its metered credits. What is the most likely explanation?
- [ ] QUERY_ATTRIBUTION_HISTORY double-counts concurrent queries
- [x] Idle warehouse time and very short queries are not attributed to individual queries
- [ ] Cloud services credits are counted twice in metering
- [ ] The view only covers SELECT statements
> Attribution excludes idle time and queries of roughly 100 ms or less, so attributed credits are expected to be lower than warehouse metering.

### A top query pattern shows low partition scan ratios, no spilling, but very high queued_overload_time. What is the best first action?
- [ ] Add a clustering key to the scanned table
- [ ] Rewrite the query to use UNION ALL
- [x] Address warehouse concurrency, for example with multi-cluster scaling or workload isolation
- [ ] Increase the result cache retention
> Overload queuing means the warehouse was saturated by concurrent work; the query itself prunes well and fits in memory, so the fix is capacity or isolation rather than query design.
