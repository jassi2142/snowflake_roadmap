# Query Anti-patterns

Most expensive Snowflake queries are not slow because the platform is slow; they are slow because the SQL forces the engine to read, move, sort or multiply far more data than the answer requires. Recognizing a small set of recurring anti-patterns lets senior engineers fix root causes in code review instead of buying bigger warehouses.

## How it works

Snowflake's performance rests on a few mechanisms: **micro-partition pruning** from min/max metadata, **columnar projection** (reading only referenced columns), **distributed joins and aggregations** in warehouse memory, and **result and warehouse caches**. Each anti-pattern below defeats one of them. The Query Profile and `GET_QUERY_OPERATOR_STATS` expose the symptom in each case.

**1. Exploding joins.** Joining on a non-unique key, an incomplete composite key, or with an accidental cross join multiplies rows. Symptom: a Join or CartesianJoin with output rows far above input rows, often followed by spilling and a DISTINCT used to "fix" duplicates. Fix the key, deduplicate the dimension first, or aggregate before joining.

**2. Functions on filter columns.** Pruning compares predicates to partition min/max values. Predicates such as `WHERE TO_CHAR(order_ts, 'YYYY-MM') = '2026-10'` or `WHERE amount::VARCHAR = '100'` may prevent the optimizer from using that metadata. Rewrite as a range on the raw column: `order_ts >= '2026-10-01' AND order_ts < '2026-11-01'`. Symptom: partitions scanned close to partitions total.

**3. SELECT * on wide tables.** Columnar storage reads only referenced columns. `SELECT *` reads all of them, increases network transfer and result size, and in materialized views it freezes the column list at creation time. Project only what you need, especially in CTEs and views consumed by many queries.

**4. ORDER BY without LIMIT.** A global sort of a large result is expensive, can spill, and is rarely needed by the consumer. With `LIMIT`, Snowflake can use a SortWithLimit operator that keeps only the top rows. Sort in the presentation layer or add a limit.

**5. UNION instead of UNION ALL.** `UNION` removes duplicates, which requires an extra aggregation over the combined set. If inputs cannot overlap, or duplicates are acceptable, `UNION ALL` avoids that work.

**6. Row-by-row processing.** Loops in procedures issuing single-row INSERT or UPDATE statements create many tiny transactions, compilation overhead and micro-partition churn. Use set-based `INSERT ... SELECT` or `MERGE`.

**7. Non-deterministic or changing SQL text.** Embedding `CURRENT_TIMESTAMP()` or generating slightly different SQL for identical requests prevents result cache reuse.

**8. Late filtering.** Filtering after a join or window function means the expensive step processes rows that are later discarded. The optimizer pushes down many predicates, but not through every construct (for example, filters on window function output). Filter early and explicitly.

The design principle: reduce data as early as possible, keep predicates sargable against stored columns, and make sure every join has a known cardinality.

## Example

An anti-pattern query and its rewrite:

```sql
-- Anti-pattern: function on filter column, SELECT *, UNION, global sort
SELECT * FROM sales.public.orders
WHERE TO_CHAR(order_ts, 'YYYY-MM') = '2026-10'
UNION
SELECT * FROM sales.public.orders_archive
WHERE TO_CHAR(order_ts, 'YYYY-MM') = '2026-10'
ORDER BY order_ts;

-- Rewrite: range predicate, projection, UNION ALL, bounded sort
SELECT order_id, customer_id, order_ts, amount
FROM sales.public.orders
WHERE order_ts >= '2026-10-01' AND order_ts < '2026-11-01'
UNION ALL
SELECT order_id, customer_id, order_ts, amount
FROM sales.public.orders_archive
WHERE order_ts >= '2026-10-01' AND order_ts < '2026-11-01'
ORDER BY order_ts DESC
LIMIT 1000;
```

Find queries that scan nearly every partition of large tables, a common symptom of non-sargable predicates:

```sql
SELECT query_parameterized_hash,
       COUNT(*) AS runs,
       AVG(partitions_scanned / NULLIF(partitions_total, 0)) AS scan_ratio,
       ANY_VALUE(LEFT(query_text, 150)) AS sample
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND partitions_total > 10000
GROUP BY 1
HAVING scan_ratio > 0.9
ORDER BY runs DESC;
```

## Best practices

- Validate join cardinality explicitly (for example, check that dimension keys are unique) before productionizing a query.
- Keep filter predicates on raw columns; push transformations into the comparison value, not the column.
- Require explicit column lists in shared views and pipelines.
- Default to `UNION ALL`; use `UNION` only when deduplication is a requirement.
- Make the Query Profile part of code review for heavy queries.

## Common pitfalls

- Adding `DISTINCT` to hide duplicates produced by a bad join, which adds cost instead of fixing the cause.
- Assuming the optimizer will always rewrite a non-sargable predicate.
- Scaling up the warehouse to compensate for an anti-pattern, which raises cost permanently.
- Over-correcting: `SELECT *` on a small table during exploration is fine; the problem is wide tables in production paths.

## Learn more

- [GET_QUERY_OPERATOR_STATS](https://docs.snowflake.com/en/sql-reference/functions/get_query_operator_stats)
- [Clustering Keys & Clustered Tables](https://docs.snowflake.com/en/user-guide/tables-clustering-keys)
- [Queries too large to fit in memory](https://docs.snowflake.com/en/user-guide/performance-query-warehouse-memory)

## Knowledge check

### A query filters with WHERE DATE_TRUNC('month', event_ts) = '2026-10-01' on a table clustered by event_ts, and scans 98% of partitions. What is the best rewrite?
- [ ] Add DISTINCT to reduce rows
- [x] Use a range predicate: event_ts >= '2026-10-01' AND event_ts < '2026-11-01'
- [ ] Increase the warehouse size
- [ ] Wrap the query in a CTE
> A range on the raw column lets the optimizer compare directly against partition min/max metadata, restoring pruning.

### Two staging tables contain disjoint sets of IDs and are combined with UNION. What is the effect of switching to UNION ALL?
- [ ] Results will contain duplicates that did not exist before
- [x] Results are identical, and the deduplication step is avoided
- [ ] The query will fail because the column types differ
- [ ] Pruning will stop working
> When inputs cannot overlap, UNION's deduplication is pure overhead, and UNION ALL returns the same rows more cheaply.

### A reviewer sees a query that joins facts to a dimension and then applies SELECT DISTINCT; the Join operator outputs 40 times its input rows. What is the root-cause fix?
- [ ] Keep DISTINCT and move to a larger warehouse
- [ ] Replace DISTINCT with ORDER BY
- [x] Correct the join so the dimension key is unique, for example by deduplicating the dimension or completing the composite key
- [ ] Add a clustering key on the dimension table
> The row multiplication comes from a non-unique join key; fixing the key removes both the explosion and the need for DISTINCT.
