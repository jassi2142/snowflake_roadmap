# Skip reprocessing history with FROZEN WHERE

topics: dynamic-tables, storage-cost
tags: cost, elt, performance
level: advanced

A frozen region tells Snowflake that dynamic table rows matching a predicate will no longer change, so refreshes (and reinitializations) only recompute the active region. This keeps refresh cost flat as history grows.

```sql
USE SCHEMA my_db.pipelines;

-- Rows with order_date older than 30 days are frozen; only recent rows are refreshed
CREATE OR REPLACE DYNAMIC TABLE dt_order_lines
  TARGET_LAG = '10 minutes'
  WAREHOUSE = my_wh
  FROZEN WHERE (order_date < CURRENT_TIMESTAMP() - INTERVAL '30 days')
AS
SELECT o.order_id, o.customer_id, o.order_date, l.product_id, l.qty * l.unit_price AS line_total
FROM my_db.bronze.orders o
JOIN my_db.bronze.order_lines l ON l.order_id = o.order_id;

-- Which rows are frozen?
SELECT COUNT_IF(METADATA$IS_FROZEN) AS frozen_rows,
       COUNT_IF(NOT METADATA$IS_FROZEN) AS active_rows
FROM dt_order_lines;

-- The predicate appears in the immutable_where column
SHOW DYNAMIC TABLES LIKE 'DT_ORDER_LINES';

-- Expanding the frozen region does not reinitialize; shrinking or removing it does
ALTER DYNAMIC TABLE dt_order_lines
  SET FROZEN WHERE (order_date < CURRENT_TIMESTAMP() - INTERVAL '7 days');

-- Late correction to an old (frozen) row without a full reprocess
DELETE FROM dt_order_lines WHERE customer_id = 105;   -- e.g. a GDPR erasure
```

## Notes
- The predicate is ignored on the initial refresh, so the first build still computes everything. Use `BACKFILL FROM <table>` at creation to copy historical rows instead.
- Predicate columns must be dynamic table output columns; no subqueries, UDFs, metadata columns, or nondeterministic functions other than timestamp functions.
- Changes to base rows that fall in the frozen region are not reflected. Only freeze data that is truly final, or fix it with DML as shown.
- The older `IMMUTABLE WHERE` syntax still works; `FROZEN WHERE` is the current name.

## References
- [Frozen regions and backfill](https://docs.snowflake.com/en/user-guide/dynamic-tables/frozen-regions)
- [CREATE DYNAMIC TABLE](https://docs.snowflake.com/en/sql-reference/sql/create-dynamic-table)
- [ALTER DYNAMIC TABLE](https://docs.snowflake.com/en/sql-reference/sql/alter-dynamic-table)
