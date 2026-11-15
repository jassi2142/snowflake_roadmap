# Aggregation & Projection Policies

Aggregation and projection policies are privacy policies that constrain *how* data can be queried rather than *which* values are visible. An aggregation policy forces queries to return only grouped results above a minimum group size; a projection policy prevents a column from appearing in query output while still allowing it in filters and joins. Together they let providers share data for analytics, matching, and clean-room style use cases without exposing individual records.

## How it works

Both policy types require **Enterprise Edition or higher** and are schema-level objects with a fixed signature.

### Aggregation policies

```sql
CREATE [ OR REPLACE ] AGGREGATION POLICY <name>
  AS () RETURNS AGGREGATION_CONSTRAINT -> <body>;
```

The body returns either `NO_AGGREGATION_CONSTRAINT()` (unrestricted) or `AGGREGATION_CONSTRAINT(MIN_GROUP_SIZE => n)`. The body cannot reference UDFs, tables, or views, so conditions are typically based on context functions such as `CURRENT_ROLE()`.

Behavior of an aggregation-constrained table or view:

- Queries must aggregate, using only allowed functions: `AVG`, `COUNT` (including `DISTINCT`), `HLL`, and `SUM`.
- Groups smaller than the minimum are folded into a **remainder group** whose GROUP BY key is `NULL`.
- Not allowed: `GROUP BY ROLLUP/CUBE/GROUPING SETS`, window functions, recursive CTEs, `PIVOT`, most set operators (`UNION ALL` is allowed), and non-`TRY_` casts in the select list.
- In joins, each group must include at least the minimum number of rows **from each constrained table**, not just the joined row count.
- A table or view can have only one aggregation policy. Views with aggregation policies are treated as secure views, and the base table is not itself constrained.
- Materialized views cannot be built on aggregation-constrained objects; external tables cannot be protected.

**Entity-level privacy.** Without an entity key, the policy protects individual rows. If one person appears in many rows, a group of five rows might describe one person. Attaching the policy with an **entity key** (for example `user_id`) makes Snowflake count distinct entities per group instead.

**Trust model.** Snowflake explicitly notes that aggregation policies do not guarantee protection against a determined attacker running many crafted queries. Use them with partners you already trust and monitor access history.

### Projection policies

```sql
CREATE [ OR REPLACE ] PROJECTION POLICY <name>
  AS () RETURNS PROJECTION_CONSTRAINT -> <body>;
```

The body calls `PROJECTION_CONSTRAINT(ALLOW => TRUE|FALSE, ENFORCEMENT => 'FAIL'|'NULLIFY')`. With `ALLOW => FALSE`, a query that projects the column in its outermost result either fails (the default, `FAIL`) or returns `NULL` for every row (`NULLIFY`). The column can still be used in `WHERE`, `JOIN`, and similar clauses, which is ideal for overlap analysis on identifiers such as hashed emails. If a column of an aggregation-constrained table has a projection policy, it cannot be used as the argument of `COUNT`.

Both policy types can be attached through tags (tag-based aggregation and projection policies), and they combine with masking and row access policies; a query must satisfy all of them.

## Example

Require groups of at least 5 rows for everyone except an admin role:

```sql
CREATE AGGREGATION POLICY privacy.agg_policies.min5
  AS () RETURNS AGGREGATION_CONSTRAINT ->
    CASE
      WHEN CURRENT_ROLE() = 'PRIVACY_ADMIN' THEN NO_AGGREGATION_CONSTRAINT()
      ELSE AGGREGATION_CONSTRAINT(MIN_GROUP_SIZE => 5)
    END;

ALTER TABLE shared.public.customer_events
  SET AGGREGATION POLICY privacy.agg_policies.min5;

-- Allowed: aggregated by a coarse dimension
SELECT region, COUNT(*) AS events FROM shared.public.customer_events GROUP BY region;
```

Allow joining on an email hash but never returning it:

```sql
CREATE OR REPLACE PROJECTION POLICY privacy.proj_policies.no_project
  AS () RETURNS PROJECTION_CONSTRAINT ->
    PROJECTION_CONSTRAINT(ALLOW => FALSE, ENFORCEMENT => 'NULLIFY');

ALTER TABLE shared.public.customer_events
  MODIFY COLUMN email_hash SET PROJECTION POLICY privacy.proj_policies.no_project;
```

Replace an aggregation policy atomically:

```sql
ALTER TABLE shared.public.customer_events
  SET AGGREGATION POLICY privacy.agg_policies.min10 FORCE;
```

## Best practices

- Use entity keys whenever an individual can appear in multiple rows; row-level thresholds alone underestimate re-identification risk.
- Pair projection policies on join keys with aggregation policies on the same table for overlap and audience-sizing use cases.
- Use `FORCE` to replace policies so there is no unprotected interval.
- Monitor consumer queries via access history and keep thresholds conservative for external sharing.

## Common pitfalls

- Expecting unsupported aggregates (for example `MIN`, `MAX`, `MEDIAN`) or window functions to work against constrained tables.
- Assuming a large joined group satisfies the policy when most rows come from a single constrained record.
- Applying an aggregation policy to a view and forgetting the base table remains queryable without restriction.
- Choosing `FAIL` enforcement for projection policies in BI tools that issue `SELECT *`, causing every dashboard query to error.

## Learn more

- [Aggregation policies](https://docs.snowflake.com/en/user-guide/aggregation-policies)
- [Projection policies](https://docs.snowflake.com/en/user-guide/projection-policies)
- [Implementing entity-level privacy with aggregation policies](https://docs.snowflake.com/en/user-guide/aggregation-policies-entity-privacy)

## Knowledge check

### A purchases table has many rows per customer and an aggregation policy with MIN_GROUP_SIZE => 10 and no entity key. A consumer groups by zip code. What is the main privacy risk?
- [ ] The query will fail because GROUP BY is not allowed
- [x] A group can meet the 10-row threshold while describing only one or two customers
- [ ] Small groups will be returned with their real zip code
- [ ] SUM is not an allowed aggregate
> Without an entity key the policy protects rows, not people; an entity key makes Snowflake count distinct entities per group.

### A partner must match their customer list against yours on a hashed email column but must never retrieve your hashes. Which control fits best?
- [ ] A masking policy that returns NULL for the partner role
- [x] A projection policy on the hash column, so it can be used in joins but not projected
- [ ] A row access policy that returns FALSE for the partner role
- [ ] Removing the column from the share
> Projection policies block a column from query output while still allowing it in join and filter conditions; masking would change the values used in the join.

### An aggregation-constrained table returns a row with a NULL region and a count. What does this row represent?
- [ ] Rows whose region column is actually NULL
- [ ] An error placeholder for invalid groups
- [x] A remainder group combining all groups smaller than the minimum group size
- [ ] Rows filtered by a row access policy
> Snowflake merges undersized groups into a remainder group and sets its grouping key to NULL because it spans multiple groups.
