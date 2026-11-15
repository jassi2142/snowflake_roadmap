# Dynamic Tables

A dynamic table materializes the result of a SELECT query and keeps it up to date automatically. You declare the query and how fresh the data must be, and Snowflake handles dependency tracking, scheduling, and incremental refresh, replacing much of the hand-written orchestration that streams and tasks require.

## How it works

You define a dynamic table with three main settings:

- **The query** (`AS SELECT ...`): what the table contains. Joins, aggregations, and window functions are supported; stored procedures and external functions are not.
- **`TARGET_LAG`**: a staleness target, not a refresh interval. `'10 minutes'` means data should be no more than 10 minutes behind the base tables. The minimum is 60 seconds, and the target is best effort, not a guarantee. The keyword `DOWNSTREAM` means "refresh only when a downstream dynamic table needs fresh data."
- **`WAREHOUSE`**: the compute used for refreshes.

**Refresh modes.** `INCREMENTAL` processes only changed rows; `FULL` recomputes the whole result; `AUTO` lets Snowflake pick at creation time based on whether the query supports incremental refresh. Snowflake also documents `ADAPTIVE` and `CUSTOM_INCREMENTAL` modes for advanced cases. Set the mode explicitly in production so behavior does not change unexpectedly.

**Pipelines.** When dynamic tables read from each other, Snowflake infers the dependency graph from the queries, refreshes upstream tables first, and keeps a consistent snapshot across the pipeline. Target lag is measured relative to the base tables at the root of the pipeline. A downstream table cannot have a shorter lag than its upstream, and a `DOWNSTREAM` table with no downstream consumers never refreshes automatically.

**Refreshes** are applied atomically, so readers never see partial results. If a refresh is still running when the next would start, Snowflake waits rather than running concurrently. You can force one with `ALTER DYNAMIC TABLE ... REFRESH` and pause with `ALTER DYNAMIC TABLE ... SUSPEND`.

**Costs** include warehouse compute for refreshes, cloud services for scheduling and change tracking (shorter lag means more scheduling work), and storage.

## Example

A two-level pipeline: the intermediate table refreshes only when needed, and the reporting table targets 10-minute freshness.

```sql
CREATE OR REPLACE DYNAMIC TABLE dt_orders_clean
  TARGET_LAG = DOWNSTREAM
  WAREHOUSE = transform_wh
  REFRESH_MODE = INCREMENTAL
AS
  SELECT order_id, customer_id, order_date,
         quantity * unit_price AS line_total
  FROM raw_orders
  WHERE order_status <> 'returned';

CREATE OR REPLACE DYNAMIC TABLE dt_daily_revenue
  TARGET_LAG = '10 minutes'
  WAREHOUSE = transform_wh
  REFRESH_MODE = INCREMENTAL
AS
  SELECT order_date, customer_id, SUM(line_total) AS revenue
  FROM dt_orders_clean
  GROUP BY order_date, customer_id;
```

Check refresh history and the mode Snowflake actually chose:

```sql
SHOW DYNAMIC TABLES LIKE 'dt_%';

SELECT name, state, refresh_action, refresh_start_time
FROM TABLE(INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY())
ORDER BY refresh_start_time DESC
LIMIT 20;
```

## Best practices

- Use `TARGET_LAG = DOWNSTREAM` for intermediate tables and a time-based lag only on the tables people query.
- Choose the longest lag the business accepts; shorter lag costs more.
- Specify `REFRESH_MODE` explicitly and confirm incremental refresh is in effect for large tables.
- Keep each dynamic table's query simple and layer them; this improves incremental refresh eligibility and debugging.
- Use a dedicated warehouse for refreshes so cost is easy to attribute.

## Common pitfalls

- Treating target lag as a cron schedule or a hard SLA. It is a best-effort freshness target.
- Setting `DOWNSTREAM` on the final table in a pipeline, so it never refreshes.
- Using non-deterministic or unsupported constructs that force full refreshes on large tables.
- Expecting sub-minute freshness. Use streams with triggered tasks or other ingestion options for that.

## Learn more

- [Dynamic tables](https://docs.snowflake.com/en/user-guide/dynamic-tables/overview)
- [Set the target lag for a dynamic table](https://docs.snowflake.com/en/user-guide/dynamic-tables/target-lag)
- [Dynamic table refresh modes](https://docs.snowflake.com/en/user-guide/dynamic-tables/refresh-modes)

## Knowledge check

### What does `TARGET_LAG = '15 minutes'` mean?
- [ ] The table refreshes exactly every 15 minutes
- [x] Snowflake aims to keep data no more than 15 minutes behind the base tables
- [ ] Refreshes are guaranteed to complete within 15 minutes
- [ ] The table keeps 15 minutes of history
> Target lag is a best-effort staleness target; Snowflake schedules refreshes to try to stay within it.

### In a pipeline A -> B, A has `TARGET_LAG = '10 minutes'` and B has `TARGET_LAG = DOWNSTREAM`. Nothing reads from B. What happens?
- [ ] B refreshes every 10 minutes along with A
- [ ] Snowflake raises an error at creation
- [x] A refreshes, but B never refreshes automatically
- [ ] B refreshes once per day by default
> DOWNSTREAM means B refreshes only when a downstream consumer needs it; with no consumers, it never refreshes automatically.

### A team needs data fresher than 30 seconds. Are dynamic tables a good fit?
- [ ] Yes, set TARGET_LAG = '30 seconds'
- [ ] Yes, use REFRESH_MODE = FULL
- [x] No, the minimum target lag is 60 seconds
- [ ] Yes, if the warehouse is large enough
> Dynamic tables do not support target lag below 60 seconds; lower-latency needs call for other approaches.
