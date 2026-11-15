# Cost Attribution

Cost attribution assigns Snowflake spend to the teams, products or environments that caused it. It is the data foundation for showback and chargeback, and it turns an account-level bill into numbers that owners can act on. The hard part is not the SQL; it is choosing an attribution model that is fair, explainable and stable as workloads change.

## How it works

Snowflake's recommended approach combines two mechanisms:

- **Object tags** on resources and users (for example a `cost_center` tag on warehouses and users). Tags are schema-level objects and can be restricted with `ALLOWED_VALUES`. For multi-account organizations, create tags in a key account and replicate the tag database to other accounts. User tags can be applied automatically through SCIM provisioning.
- **Query tags** (`QUERY_TAG` session parameter) for applications that run queries on behalf of users from several departments.

The documentation describes three scenarios, and each needs a different join:

1. **Dedicated resources** – a warehouse used by one department. Join `TAG_REFERENCES` (domain `WAREHOUSE`) to `WAREHOUSE_METERING_HISTORY` on `object_id = warehouse_id`. All metered credits, including idle time, go to the owner.
2. **Shared warehouses** – users from several departments on one warehouse. Join `TAG_REFERENCES` (domain `USER`) to `QUERY_ATTRIBUTION_HISTORY` on user name and sum `credits_attributed_compute`.
3. **Shared applications** – one service user issues queries for many teams. Group `QUERY_ATTRIBUTION_HISTORY` by `query_tag`.

**Design decisions for architects:**

- **Idle time.** Per-query attribution excludes warehouse idle time and very short queries. You must decide whether to (a) report idle as a platform overhead line, (b) spread it proportionally to each team's attributed usage, or (c) charge it to the warehouse owner. Proportional spreading reconciles to the bill; an overhead line keeps teams accountable only for what they control. Choose deliberately and document it.
- **What per-query attribution misses.** `QUERY_ATTRIBUTION_HISTORY` excludes cloud services, storage, data transfer, serverless features and AI token costs. Serverless and storage costs are attributed through the objects that incur them (tables, pipes, tasks, materialized views), typically using tags on the database or schema plus the feature-specific history views.
- **Granularity vs. stability.** Dedicated warehouses per team give the simplest, most auditable attribution but can waste capacity. Shared warehouses are more efficient but make attribution model-dependent.
- **Latency.** `QUERY_ATTRIBUTION_HISTORY` can lag up to 8 hours, so daily reports should run on settled data.
- **Untagged spend.** Always report an "untagged" bucket; its size measures the health of your tagging process.

## Example

Dedicated warehouses: last month's credits by `cost_center` tag:

```sql
SELECT COALESCE(tr.tag_value, 'untagged') AS cost_center,
       SUM(wmh.credits_used_compute)       AS compute_credits
FROM snowflake.account_usage.warehouse_metering_history wmh
LEFT JOIN snowflake.account_usage.tag_references tr
  ON wmh.warehouse_id = tr.object_id
 AND tr.domain = 'WAREHOUSE'
 AND tr.tag_name = 'COST_CENTER'
WHERE wmh.start_time >= DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE()))
  AND wmh.start_time <  DATE_TRUNC('month', CURRENT_DATE())
GROUP BY 1
ORDER BY 2 DESC;
```

Shared warehouses: per-department query cost, with idle time spread proportionally:

```sql
WITH metered AS (
  SELECT SUM(credits_used_compute) AS total_credits
  FROM snowflake.account_usage.warehouse_metering_history
  WHERE warehouse_name = 'SHARED_WH'
    AND start_time >= DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE()))
    AND start_time <  DATE_TRUNC('month', CURRENT_DATE())
),
by_dept AS (
  SELECT COALESCE(tr.tag_value, 'untagged') AS department,
         SUM(qah.credits_attributed_compute) AS query_credits
  FROM snowflake.account_usage.query_attribution_history qah
  LEFT JOIN snowflake.account_usage.tag_references tr
    ON tr.object_name = qah.user_name
   AND tr.domain = 'USER'
   AND tr.tag_name = 'COST_CENTER'
  WHERE qah.warehouse_name = 'SHARED_WH'
    AND qah.start_time >= DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE()))
    AND qah.start_time <  DATE_TRUNC('month', CURRENT_DATE())
  GROUP BY 1
)
SELECT d.department,
       d.query_credits,
       d.query_credits / SUM(d.query_credits) OVER () * m.total_credits AS credits_incl_idle
FROM by_dept d CROSS JOIN metered m
ORDER BY credits_incl_idle DESC;
```

Applications: set a tag per request context so costs can be grouped later:

```sql
ALTER SESSION SET QUERY_TAG = 'COST_CENTER=finance';
```

## Best practices

- Automate tagging at creation time (infrastructure as code, SCIM for users); manual tagging decays.
- Use `ALLOWED_VALUES` on attribution tags to prevent typos that fragment reports.
- Publish the attribution methodology, including idle-time treatment, and keep it stable between periods.
- Reconcile attributed totals to `METERING_DAILY_HISTORY` each month.
- Use the same tags for budgets so that alerting and reporting agree.

## Common pitfalls

- Presenting `credits_attributed_compute` totals as the full bill.
- Using free-form `QUERY_TAG` strings without a convention, making aggregation unreliable.
- Ignoring serverless and storage costs, which can be a large share of spend.
- Joining tags without filtering on `domain`, causing objects in different domains with the same ID to collide.
- Running reports before `QUERY_ATTRIBUTION_HISTORY` has caught up.

## Learn more

- [Attributing cost](https://docs.snowflake.com/en/user-guide/cost-attributing)
- [QUERY_ATTRIBUTION_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/query_attribution_history)

## Knowledge check

### A shared BI service account runs queries for Finance, Sales and HR users. Which attribution mechanism is most appropriate?
- [ ] Tag the BI warehouse with one cost center
- [ ] Tag the service user with one cost center
- [x] Set QUERY_TAG per request to the requesting team and group QUERY_ATTRIBUTION_HISTORY by query_tag
- [ ] Use TABLE_STORAGE_METRICS
> When one application issues queries for many departments, user and warehouse tags cannot distinguish them; query tags carry the team context per query.

### Department totals from QUERY_ATTRIBUTION_HISTORY sum to 70% of the shared warehouse's metered credits. What is the most defensible way to close the gap in a chargeback model?
- [ ] Ignore the difference; it is a reporting error
- [x] Treat the remainder as idle time and either distribute it proportionally to attributed usage or report it as a platform overhead line, per a documented policy
- [ ] Charge the remainder to whichever department ran the most queries
- [ ] Re-run the report with SELECT * to include missing rows
> Per-query attribution excludes idle time and very short queries by design, so the gap is expected and must be handled by an explicit, documented allocation policy.

### Which cost will not appear in credits_attributed_compute and needs a separate attribution path?
- [ ] Warehouse time spent executing a query on a multi-cluster warehouse
- [x] Automatic Clustering and Snowpipe serverless costs
- [ ] Warehouse credits from autoscaling during a query
- [ ] Gaps between two queries within the same minute on a cluster
> QUERY_ATTRIBUTION_HISTORY covers warehouse compute only; serverless features, storage, cloud services and data transfer must be attributed through their own views and object tags.
