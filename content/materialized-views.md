# Materialized Views

A materialized view stores the pre-computed result of a query and keeps it automatically up to date as the base table changes. It can make frequent, expensive aggregations or filters dramatically faster, but it adds storage and background maintenance cost, and it requires **Enterprise Edition**.

## How it works

When you create a materialized view, Snowflake runs the defining query (similar to a CREATE TABLE AS SELECT) and stores the result. After that, a **background service** maintains it: inserts in the base table trigger a *refresh* and deletes trigger a *compaction*. You do not schedule anything.

Results are always current. If the view is behind the base table when you query it, Snowflake uses the up-to-date parts of the view and reads newer data from the base table.

The **optimizer can rewrite queries** against the base table to use a materialized view automatically, even if the query does not reference the view. You can see this in EXPLAIN output or the Query Profile.

**Key limitations** (current documentation):

- A materialized view can query **only a single table**; joins, including self-joins, are not supported.
- It cannot query another view, a materialized view, a hybrid table, a dynamic table or a UDTF.
- It cannot include UDFs, window functions, HAVING, ORDER BY, LIMIT, nested subqueries, GROUP BY ROLLUP/CUBE/GROUPING SETS, or MINUS/EXCEPT/INTERSECT.
- Only some aggregates are supported, including COUNT, COUNT_IF, SUM, AVG, MIN, MAX, APPROX_COUNT_DISTINCT, STDDEV and VARIANCE variants. GROUP BY keys must appear in the SELECT list.
- Functions must be deterministic (no CURRENT_TIMESTAMP).
- You cannot run DML or TRUNCATE on a materialized view, and Time Travel queries against it are not supported.

**Cost.** You pay for the view's storage and for serverless maintenance credits, which appear under a Snowflake-provided warehouse named `MATERIALIZED_VIEW_MAINTENANCE`. Resource monitors do not control this cost. Clustering a materialized view adds more maintenance cost.

**Base table changes.** Adding columns does not affect the view (new columns are not added, even with SELECT *). Dropping or changing a base table column suspends the view permanently; you must recreate it.

## Example

Pre-aggregate daily revenue from a large orders table:

```sql
CREATE OR REPLACE MATERIALIZED VIEW sales.public.mv_daily_revenue AS
SELECT order_date,
       region,
       SUM(amount) AS revenue,
       COUNT(*)    AS order_count
FROM sales.public.orders
GROUP BY order_date, region;
```

This query against the base table may be rewritten to use the view automatically:

```sql
SELECT region, SUM(amount)
FROM sales.public.orders
WHERE order_date >= '2026-01-01'
GROUP BY region;
```

Check freshness and maintenance cost:

```sql
SHOW MATERIALIZED VIEWS LIKE 'MV_DAILY_REVENUE' IN SCHEMA sales.public;

SELECT TO_DATE(start_time) AS day, SUM(credits_used) AS credits
FROM snowflake.account_usage.materialized_view_refresh_history
WHERE table_name = 'MV_DAILY_REVENUE'
  AND start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 1;
```

The `refreshed_on` and `behind_by` columns of SHOW MATERIALIZED VIEWS show how current the view is.

## Best practices

- Use materialized views when results are small relative to the base table, expensive to compute, queried often, and the base table changes infrequently.
- Select explicit columns instead of SELECT *.
- Batch DML on the base table to reduce maintenance work.
- Measure query cost before and after, and include the view's maintenance credits in the comparison.
- If data is accessed mostly through the view, consider clustering the view rather than the base table.
- Use fully qualified base table names in the definition.

## Common pitfalls

- Creating a materialized view on a table that changes constantly, so maintenance costs exceed the savings.
- Expecting joins to work; use a dynamic table or a regular view on top of the materialized view instead.
- Dropping a base table column and being surprised that the view must be recreated.
- Assuming resource monitors will cap maintenance spend.
- Treating a materialized view as a replacement for the result cache; the result cache is faster when the exact query repeats and data has not changed.

## Learn more

- [Working with Materialized Views](https://docs.snowflake.com/en/user-guide/views-materialized)
- [CREATE MATERIALIZED VIEW](https://docs.snowflake.com/en/sql-reference/sql/create-materialized-view)

## Knowledge check

### You need a pre-computed result that joins orders with customers and refreshes automatically. Why is a materialized view not suitable?
- [ ] Materialized views cannot contain aggregates
- [x] Materialized views can query only a single table and do not support joins
- [ ] Materialized views refresh only once a day
- [ ] Materialized views require Business Critical Edition
> Materialized views are limited to a single base table; joins, including self-joins, are not supported.

### A materialized view is defined on a base table that receives thousands of small inserts per minute. What is the main risk?
- [ ] Queries return stale results
- [x] High serverless maintenance cost that can outweigh query savings
- [ ] The view becomes read-only
- [ ] The view stops being used by the optimizer
> Every base table change requires background maintenance; frequent changes drive up credits, while results always stay current.

### An analyst drops an unused column from a base table that has a materialized view. What happens to the view?
- [ ] Nothing, because the column was not used by the view
- [ ] The view is refreshed automatically without the column
- [x] The view is suspended and must be recreated
- [ ] The view is dropped automatically
> Changing or dropping any base table column suspends all materialized views on that table, even if the column was not referenced, and they cannot be resumed.
