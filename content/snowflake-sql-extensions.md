# Snowflake SQL Extensions

Beyond standard SQL, Snowflake offers several extensions that make common analytical queries shorter and easier to read. Examples include QUALIFY, GROUP BY ALL, SELECT * EXCLUDE/RENAME/REPLACE/ILIKE, PIVOT/UNPIVOT, MATCH_RECOGNIZE, and reuse of column aliases. Knowing them removes boilerplate subqueries and makes transformations easier to maintain.

## How it works

**QUALIFY** filters on the results of window functions, much as HAVING filters on aggregates. Without it, you need a subquery to filter on `ROW_NUMBER()`.

**GROUP BY ALL** groups by every item in the SELECT list that does not use an aggregate function. If every SELECT item is an aggregate, `GROUP BY ALL` is the same as leaving out GROUP BY.

**SELECT * modifiers** reshape a wide select without listing every column. They must appear in this order:

- `ILIKE 'pattern'` keeps only columns whose names match (case-insensitive). If nothing matches, the query fails to compile.
- `EXCLUDE col` or `EXCLUDE (col1, col2)` drops columns. You cannot combine ILIKE and EXCLUDE.
- `REPLACE (expr AS col)` swaps in a computed value under the same column name.
- `RENAME col AS alias` or `RENAME (a AS x, b AS y)` changes output names.

The order is ILIKE or EXCLUDE first, then REPLACE, then RENAME. With joins, qualify the star, as in `t.* EXCLUDE id`.

**Column alias reuse.** A column alias defined in the SELECT list can be referenced in other parts of the same query: WHERE, GROUP BY, and other column expressions. Avoid aliases that match the name of another column used in the query; this can cause compilation errors.

**PIVOT / UNPIVOT** rotate rows into columns and back. They are useful for reporting layouts and for normalizing wide source files.

**MATCH_RECOGNIZE** finds sequences of rows that match a regular-expression-like pattern within partitions. Examples include event funnels, V-shaped price movements, or runs of failed logins.

**Others worth knowing**

- A trailing comma in the SELECT column list is allowed.
- `GROUPING SETS`, `ROLLUP`, and `CUBE` (up to 128 grouping sets per query block).
- `LATERAL` with `FLATTEN` for semi-structured data.

## Example

Get the latest order per customer, without a subquery:

```sql
SELECT customer_id, order_id, order_ts, amount
FROM orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts DESC) = 1;
```

Reuse an alias in WHERE and GROUP BY, then group by every non-aggregate column:

```sql
SELECT DATE_TRUNC('month', order_ts) AS order_month,
       region,
       SUM(amount) AS revenue
FROM orders
WHERE order_month >= '2026-01-01'
GROUP BY ALL;
```

Reshape a wide select:

```sql
SELECT * EXCLUDE (internal_notes, etl_loaded_at)
         REPLACE (ROUND(amount, 0) AS amount)
         RENAME (cust_id AS customer_id)
FROM orders;
```

Pivot monthly revenue into columns:

```sql
SELECT *
FROM (SELECT region, MONTHNAME(order_ts) AS mon, amount FROM orders)
PIVOT (SUM(amount) FOR mon IN ('Jan', 'Feb', 'Mar')) AS p;
```

## Best practices

- Prefer QUALIFY over nested subqueries for deduplication. The intent is clearer and easier to review.
- Use GROUP BY ALL in exploratory and layered models. In critical models, list grouping columns explicitly so a new SELECT column cannot silently change the grain.
- Use `* EXCLUDE` in views that must hide a few sensitive or technical columns, but remember that new source columns will flow through automatically.
- Write a clear `DEFINE` and `PATTERN` in MATCH_RECOGNIZE, and test against small, known datasets.

## Common pitfalls

- Giving an alias the same name as a real column, which causes ambiguity or compilation errors.
- Combining `ILIKE` and `EXCLUDE`, or putting RENAME before REPLACE.
- Writing `SELECT *` over a join without qualifying EXCLUDE/RENAME to one table.
- Assuming these extensions will run unchanged on other databases when you port SQL.

## Learn more

- [SELECT (EXCLUDE, REPLACE, RENAME, ILIKE)](https://docs.snowflake.com/en/sql-reference/sql/select)
- [GROUP BY](https://docs.snowflake.com/en/sql-reference/constructs/group-by)
- [GROUP BY GROUPING SETS](https://docs.snowflake.com/en/sql-reference/constructs/group-by-grouping-sets)

## Knowledge check

### You need the most recent row per `device_id` from an events table. Which approach is the most concise valid Snowflake SQL?
- [ ] `WHERE ROW_NUMBER() OVER (...) = 1`
- [ ] `HAVING ROW_NUMBER() OVER (...) = 1`
- [x] `QUALIFY ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY event_ts DESC) = 1`
- [ ] `GROUP BY ALL` with `MAX(event_ts)`
> QUALIFY filters on window function results directly. Window functions are not allowed in WHERE or HAVING.

### Which modifier sequence after `SELECT *` is valid?
- [ ] `RENAME a AS x REPLACE (b + 1 AS b)`
- [ ] `ILIKE '%id%' EXCLUDE c`
- [x] `EXCLUDE c REPLACE (b + 1 AS b) RENAME a AS x`
- [ ] `REPLACE (b + 1 AS b) EXCLUDE c`
> EXCLUDE (or ILIKE) comes first, then REPLACE, then RENAME. ILIKE and EXCLUDE cannot be combined.

### A model uses `GROUP BY ALL`. A developer adds a non-aggregated `customer_tier` column to the SELECT list. What happens?
- [ ] The query fails to compile
- [x] `customer_tier` silently becomes a grouping column, changing the grain of the result
- [ ] The new column is ignored for grouping
- [ ] Snowflake applies ANY_VALUE to it automatically
> GROUP BY ALL groups by every non-aggregate SELECT item, so adding one changes the grouping. This is why explicit grouping is safer in critical models.
