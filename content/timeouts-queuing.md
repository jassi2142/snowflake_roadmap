# Timeouts & Queuing

Snowflake gives you three warehouse-level controls for how statements wait and run: `STATEMENT_TIMEOUT_IN_SECONDS`, `STATEMENT_QUEUED_TIMEOUT_IN_SECONDS`, and `MAX_CONCURRENCY_LEVEL`. Used together they keep runaway queries from burning credits, stop requests from waiting indefinitely in a queue, and shape how resources are shared among concurrent queries.

## How it works

When queries reach a warehouse, it estimates and reserves the resources each needs. If not enough remain, new queries **queue** until resources free up.

**STATEMENT_TIMEOUT_IN_SECONDS**

- Cancels a statement that runs longer than the value.
- Default: 172800 seconds (2 days). If set to 0, the maximum of 604800 seconds (7 days) is enforced.
- Can be set at account, user, session, and warehouse levels. When it is set for both a warehouse and a session, the lower value applies, so a short warehouse timeout cannot be bypassed by raising the session value.
- The timer covers total elapsed time, including queuing and compilation, not just execution.

**STATEMENT_QUEUED_TIMEOUT_IN_SECONDS**

- Cancels a statement that waits in a warehouse queue longer than the value.
- Default: 0, which means no queued timeout.
- Useful for interactive workloads where a stale request is worse than a fast failure.

**MAX_CONCURRENCY_LEVEL**

- A warehouse parameter that limits how many statements run concurrently on a cluster.
- Default: 8.
- Lowering it gives each query a larger share of resources, which can help large or complex queries, but increases queuing. It is a limit, not a guarantee: Snowflake may run fewer queries if they are resource-intensive.

For tasks, the separate `USER_TASK_TIMEOUT_MS` parameter also applies; when a warehouse statement timeout is set, the effective task timeout is the smaller of the two.

## Example

Protect a BI warehouse from runaway queries and stale requests:

```sql
ALTER WAREHOUSE bi_wh SET
  STATEMENT_TIMEOUT_IN_SECONDS = 600
  STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 120;
```

Allow longer ETL runs on a dedicated warehouse, with fewer but better-resourced concurrent statements:

```sql
ALTER WAREHOUSE etl_wh SET
  STATEMENT_TIMEOUT_IN_SECONDS = 14400
  MAX_CONCURRENCY_LEVEL = 4;
```

Check effective values at each level:

```sql
SHOW PARAMETERS LIKE 'STATEMENT_%' IN WAREHOUSE bi_wh;
SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS' IN ACCOUNT;
SHOW PARAMETERS LIKE 'STATEMENT_TIMEOUT_IN_SECONDS' IN SESSION;
```

Find recent queries that queued for a long time:

```sql
SELECT query_id, warehouse_name,
       queued_overload_time / 1000 AS queued_s,
       total_elapsed_time / 1000 AS elapsed_s
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time > DATEADD(day, -1, CURRENT_TIMESTAMP())
  AND queued_overload_time > 60000
ORDER BY queued_overload_time DESC;
```

## Best practices

- Always set a warehouse statement timeout lower than the 2-day default, sized to the longest legitimate query for that workload.
- Use queued timeouts on interactive warehouses so applications can retry or fail fast.
- If queuing is chronic, fix capacity (multi-cluster or a separate warehouse) instead of only adding timeouts.
- Lower `MAX_CONCURRENCY_LEVEL` only after testing; consider a dedicated warehouse or QAS for a few heavy queries instead.
- Document timeout values per warehouse so engineers understand why statements are canceled.

## Common pitfalls

- Raising the session timeout and wondering why queries still cancel; the lower warehouse value wins.
- Forgetting that queue time counts toward the statement timeout.
- Setting a queued timeout on an ETL warehouse and causing scheduled jobs to fail during normal peaks.
- Treating `MAX_CONCURRENCY_LEVEL` as a way to increase concurrency; raising it does not add compute.

## Learn more

- [Limiting concurrently running queries](https://docs.snowflake.com/en/user-guide/performance-query-warehouse-max-concurrency)
- [Overview of warehouses](https://docs.snowflake.com/en/user-guide/warehouses-overview)

## Knowledge check

### A user sets STATEMENT_TIMEOUT_IN_SECONDS = 7200 in their session, but queries on warehouse BI_WH (set to 600) still cancel after 10 minutes. Why?
- [ ] Session parameters are ignored for SELECT statements
- [x] When set at both warehouse and session level, the lower value is enforced
- [ ] The account default of 600 seconds overrides both
- [ ] The query was canceled by a resource monitor
> The effective timeout is the smaller of the warehouse and session values, so the warehouse's 600 seconds applies.

### What does STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 0 mean?
- [ ] Queued statements are canceled immediately
- [x] There is no timeout for queued statements
- [ ] Statements cannot queue on the warehouse
- [ ] The 7-day maximum applies to queuing
> A value of 0 disables the queued timeout, which is the default.

### Large, complex transformations on a warehouse run slowly while competing with each other. Which change might give each query more resources at the cost of more queuing?
- [ ] Raise MAX_CONCURRENCY_LEVEL to 16
- [x] Lower MAX_CONCURRENCY_LEVEL from 8 to 4
- [ ] Set STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 30
- [ ] Disable auto-resume
> Lowering the concurrency level means fewer queries share the warehouse, so each can receive more resources, though more queries wait.
