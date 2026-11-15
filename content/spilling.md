# Spilling & Right-sizing

Spilling happens when a query needs more memory than its warehouse can provide, so intermediate data is written to disk. It is one of the most common reasons a query runs much slower than expected, and the main signal that a warehouse may be too small for a workload. Right-sizing means choosing a warehouse size that fits the workload without paying for capacity you do not use.

## How it works

Each warehouse size provides a fixed amount of memory and local storage per cluster, and each step up roughly doubles both compute and credits per hour. Operations such as large joins, sorts, aggregations with many groups, and window functions keep intermediate results in memory.

When that memory runs out:

1. Snowflake first spills to the warehouse's **local disk**. This adds I/O and slows the query.
2. If local disk is also exhausted, it spills to **remote storage** in the cloud provider. This is much slower.

You can see spilling in two places:

- The **Query Profile** for an operator (statistics `bytes_spilled_local_storage` and `bytes_spilled_remote_storage`).
- The **QUERY_HISTORY** view columns `bytes_spilled_to_local_storage` and `bytes_spilled_to_remote_storage`.

One caveat from the documentation: when the Query Acceleration Service is enabled, Snowflake writes a small amount of data to remote storage for each eligible query, so a small non-zero remote spill value is not necessarily a problem in that case.

**Fixing spilling.** Snowflake recommends:

- Using a larger warehouse, which provides more memory and local disk.
- Processing data in smaller batches.

Reducing the data each operator handles also helps: better pruning, selecting only needed columns, correcting join conditions that explode row counts, and splitting a huge query into steps.

**Right-sizing in practice.** Warehouses bill per second with a 60-second minimum each time they start. A larger warehouse costs more per hour but can finish faster, so for memory-bound queries the total credits may be similar or even lower. A query that is not spilling and not limited by parallelism may simply cost more on a bigger warehouse without running much faster. Concurrency problems (many queries queuing) are usually better solved with multi-cluster warehouses than with a larger size.

## Example

Find the worst spilling queries in the last 14 days:

```sql
SELECT query_id,
       LEFT(query_text, 80)              AS query_start,
       warehouse_name,
       warehouse_size,
       bytes_spilled_to_local_storage,
       bytes_spilled_to_remote_storage,
       total_elapsed_time / 1000         AS elapsed_s
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD('day', -14, CURRENT_TIMESTAMP())
  AND (bytes_spilled_to_local_storage > 0 OR bytes_spilled_to_remote_storage > 0)
ORDER BY bytes_spilled_to_remote_storage DESC, bytes_spilled_to_local_storage DESC
LIMIT 20;
```

Summarize spilling by warehouse to decide which ones may be undersized:

```sql
SELECT warehouse_name,
       warehouse_size,
       COUNT(*) AS queries,
       COUNT_IF(bytes_spilled_to_remote_storage > 0) AS remote_spill_queries,
       SUM(bytes_spilled_to_local_storage) / POWER(1024, 3) AS local_spill_gb
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD('day', -14, CURRENT_TIMESTAMP())
  AND warehouse_name IS NOT NULL
GROUP BY 1, 2
ORDER BY remote_spill_queries DESC;
```

Test a larger size for a heavy batch job, then compare elapsed time and credits:

```sql
ALTER WAREHOUSE etl_wh SET WAREHOUSE_SIZE = 'LARGE';
```

## Best practices

- Fix the query first if a join is exploding or the scan is not pruned; a bigger warehouse only hides those problems.
- Treat remote spilling as a priority; local spilling on occasional queries may be acceptable.
- Separate memory-heavy batch jobs from interactive workloads so each can have a suitable size.
- Compare both runtime and credits when testing sizes; choose the smallest size that meets the time requirement.
- Use the Query Profile to find which operator spills.

## Common pitfalls

- Scaling up every warehouse when only a few queries spill.
- Using a bigger size to fix queuing caused by concurrency instead of using multi-cluster warehouses.
- Ignoring the QAS caveat and chasing tiny remote spill values.
- Leaving a warehouse at a larger size after a one-off job, paying the higher rate for all later work.

## Learn more

- [Queries too large to fit in memory](https://docs.snowflake.com/en/user-guide/performance-query-warehouse-memory)
- [Optimizing warehouses for performance](https://docs.snowflake.com/en/user-guide/performance-query-warehouse)

## Knowledge check

### A nightly job spills 400 GB to remote storage on a Medium warehouse. What is the most appropriate first step after confirming the joins are correct?
- [ ] Enable the result cache
- [x] Test the job on a larger warehouse size or process the data in smaller batches
- [ ] Convert the warehouse to multi-cluster
- [ ] Reduce AUTO_SUSPEND
> Remote spilling means the operation does not fit in the warehouse's memory and local disk; Snowflake recommends a larger warehouse or smaller batches.

### Many short dashboard queries are queuing on a Small warehouse, and none of them spill. What is the better fix?
- [ ] Increase the size to 2X-Large
- [x] Use a multi-cluster warehouse to add capacity for concurrent queries
- [ ] Add a clustering key to every table
- [ ] Disable Query Acceleration
> Queuing without spilling indicates a concurrency limit rather than a memory problem, which multi-cluster scaling addresses.

### Which statement about spilling is correct?
- [ ] Spilling goes to remote storage first, then local disk
- [x] Spilling goes to local disk first and to remote storage only if local disk is insufficient
- [ ] Spilling only happens in Standard Edition
- [ ] Spilling has no effect on performance
> Snowflake spills to the warehouse's local disk first and then to remote cloud storage, with remote spilling causing the larger slowdown.
