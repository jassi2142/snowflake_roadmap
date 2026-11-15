# Views

A view is a named query that you can use like a table. Views simplify complex logic, give users a stable interface over changing tables, and limit which columns or rows people can see. Snowflake supports standard (non-materialized) views, secure views, and materialized views.

## How it works

**Standard views**

A standard view stores only its SQL definition. Each time you query the view, Snowflake runs the underlying query, so the results are always current. It also means the view costs compute every time you query it. Views can reference tables and other views, and can be used anywhere a table is used in a query.

**Secure views**

A secure view is created with `CREATE SECURE VIEW`. It hides its definition from users who do not own it. It also stops the optimizer from using certain techniques that could reveal data from the underlying tables. Secure views are commonly used for data sharing and to restrict access to sensitive rows. The trade-off is that some optimizations are turned off, so secure views can be slower than standard views.

**Materialized views**

A materialized view stores the precomputed results of its query, and Snowflake keeps those results up to date in the background as the base table changes. Queries against it can be much faster, but you pay for the storage and for the automatic maintenance.

- Materialized views require **Enterprise Edition or higher**.
- They support a narrower set of SQL than standard views. For example, they are limited to a single base table, so no joins.
- They work best for expensive aggregations or filters on large tables that are queried often but change relatively little.

**Access.** To query a view, a role needs `SELECT` on the view, along with `USAGE` on its database and schema. The view's owner must have access to the underlying objects.

## Example

A standard view that hides technical columns and reshapes the data for analysts:

```sql
CREATE OR REPLACE VIEW analytics.sales.v_orders AS
SELECT order_id,
       customer_id,
       amount,
       DATE_TRUNC('month', order_ts) AS order_month
FROM raw.sales.orders
WHERE status <> 'CANCELLED';
```

A secure view that shows each region manager only their own region's rows. It assumes a mapping table of roles to regions.

```sql
CREATE OR REPLACE SECURE VIEW analytics.sales.v_orders_by_region AS
SELECT o.*
FROM raw.sales.orders o
JOIN raw.sales.region_access a
  ON a.region = o.region
 AND a.role_name = CURRENT_ROLE();
```

A materialized view for a frequently queried daily total (Enterprise Edition or higher):

```sql
CREATE OR REPLACE MATERIALIZED VIEW analytics.sales.mv_daily_revenue AS
SELECT order_date, SUM(amount) AS revenue
FROM raw.sales.orders
GROUP BY order_date;
```

## Best practices

- Use standard views for reusable logic and for a stable interface over changing tables.
- Use secure views when the definition or the underlying data must stay hidden, especially for shared data.
- Use materialized views only for proven, repeated, expensive queries on slowly changing tables. Watch their maintenance cost.
- Keep view stacks shallow. Deeply nested views are hard to debug and to optimize.

## Common pitfalls

- Expecting a standard view to make queries faster. It runs the full query every time.
- Making every view secure "just in case", which can turn off optimizations and slow queries down.
- Creating a materialized view on Standard Edition, or on a table that changes constantly, which drives up maintenance cost.
- Granting `SELECT` on a view but not `USAGE` on its database and schema.

## Learn more

- [Overview of views](https://docs.snowflake.com/en/user-guide/views-introduction)

## Knowledge check

### Analysts repeatedly run the same expensive aggregation on a large, slowly changing table. Which option speeds this up while keeping results current?
- [ ] A standard view
- [ ] A secure view
- [x] A materialized view (Enterprise Edition or higher)
- [ ] A temporary table refreshed by hand
> A materialized view stores precomputed results that Snowflake maintains automatically. It requires Enterprise Edition or higher.

### You share data with a partner account and must hide both the view's SQL and any underlying data that is not exposed. Which object should you use?
- [ ] A standard view
- [x] A secure view
- [ ] A transient table
- [ ] A materialized view
> Secure views hide their definition from non-owners and prevent optimizations that could reveal underlying data.

### What does querying a standard view do?
- [ ] Reads cached results stored at view creation time
- [x] Runs the view's underlying query at query time
- [ ] Reads a copy of the data refreshed nightly
- [ ] Bypasses warehouse compute
> Standard views store only their definition, so the query runs each time the view is used.
