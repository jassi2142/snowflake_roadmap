# Workload Isolation Strategy

Workload isolation means running distinct workload classes, such as ingestion and ETL, BI dashboards, data science, and ad hoc exploration, on separate warehouses so they cannot degrade one another. Because Snowflake separates storage from compute, every warehouse sees the same data, so isolation costs nothing in data duplication and gives you independent levers for performance, concurrency, cost control, and chargeback.

## How it works

Each warehouse has its own size, cluster count, scaling policy, timeouts, auto-suspend, resource monitor, and cache. Isolating workloads lets you tune each of these to the workload's profile instead of compromising.

A typical baseline topology:

| Workload | Profile | Typical configuration |
| --- | --- | --- |
| Ingestion / COPY | Many files, moderate CPU | Small to Medium; size by file parallelism, not data volume |
| ETL / ELT transforms | Heavy joins, MERGE, scheduled | Larger single cluster, Gen2, longer statement timeout |
| BI / dashboards | Many short concurrent queries, latency-sensitive | Small to Medium multi-cluster, STANDARD scaling, short queued timeout, slightly longer auto-suspend for cache |
| Data science / Snowpark | Memory-heavy Python, training | Snowpark-optimized warehouse |
| Ad hoc analysts | Unpredictable, outliers | Moderate size with QAS, strict statement timeout |

Design trade-offs to weigh:

- **Fragmentation vs. contention.** Every additional warehouse has its own 60-second minimum per resume and its own idle tail before auto-suspend. Over-isolating (one warehouse per user or per dashboard) multiplies idle cost and dilutes cache reuse. Under-isolating causes noisy neighbors. Isolate by workload *shape* and *ownership*, not by person.
- **Scale up vs. scale out.** Batch transforms benefit from size; BI concurrency benefits from clusters (Enterprise Edition). Mixing both on one warehouse forces you to pay for the larger of each.
- **Cache locality.** Repeated BI queries benefit from a warm warehouse cache; mixing them with ETL scans evicts useful data.
- **Homogeneity.** Snowflake recommends running queries of similar complexity on the same warehouse because it makes load analysis and sizing tractable.
- **Outliers.** Rather than sizing an ad hoc warehouse for its worst query, consider QAS, which bills serverless credits only when eligible queries run.

**Chargeback** builds on isolation. When each warehouse maps to a cost owner, `WAREHOUSE_METERING_HISTORY` gives direct attribution. Object tags on warehouses (for example `cost_center`) let you aggregate by owner. For shared warehouses, the `QUERY_ATTRIBUTION_HISTORY` view attributes compute credits to individual queries, which you can roll up by user, role, or query tag. Remember that serverless features and idle time need their own allocation rules.

**Guardrails** per warehouse: a resource monitor (warehouse spend only), statement and queued timeouts, and grants that restrict USAGE to the owning roles.

## Example

Provision isolated warehouses and tag them for chargeback:

```sql
CREATE TAG IF NOT EXISTS admin.tags.cost_center;

CREATE WAREHOUSE etl_wh
  WAREHOUSE_SIZE = 'LARGE' GENERATION = '2'
  AUTO_SUSPEND = 60 AUTO_RESUME = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 14400
  WITH TAG (admin.tags.cost_center = 'data_platform');

CREATE WAREHOUSE bi_wh
  WAREHOUSE_SIZE = 'SMALL'
  MIN_CLUSTER_COUNT = 1 MAX_CLUSTER_COUNT = 6 SCALING_POLICY = 'STANDARD'
  AUTO_SUSPEND = 600 AUTO_RESUME = TRUE
  STATEMENT_TIMEOUT_IN_SECONDS = 300
  STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = 60
  WITH TAG (admin.tags.cost_center = 'analytics');

GRANT USAGE ON WAREHOUSE bi_wh TO ROLE bi_reader;
```

Monthly chargeback by cost center:

```sql
SELECT t.tag_value AS cost_center,
       ROUND(SUM(m.credits_used), 1) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY m
JOIN SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES t
  ON t.object_name = m.warehouse_name
 AND t.domain = 'WAREHOUSE'
 AND t.tag_name = 'COST_CENTER'
WHERE m.start_time >= DATE_TRUNC(month, CURRENT_DATE)
GROUP BY 1
ORDER BY 2 DESC;
```

Per-user attribution inside a shared warehouse:

```sql
SELECT user_name, ROUND(SUM(credits_attributed_compute), 2) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
WHERE warehouse_name = 'ADHOC_WH'
  AND start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 2 DESC;
```

## Best practices

- Isolate by workload class and owning team; consolidate within a class to keep warehouses busy.
- Codify warehouse definitions (size, timeouts, tags, monitors) in infrastructure-as-code so new teams inherit guardrails.
- Review utilization and queuing per warehouse; merge warehouses that are rarely busy and split those with chronic queuing from mixed workloads.
- Set default warehouses per user or service account so workloads land in the right place.
- Define chargeback rules for serverless and cloud services costs, which do not map to a warehouse.

## Common pitfalls

- One warehouse per user, producing many idle tails and minimum charges.
- A single shared X-Large for everything, where ETL spikes cause dashboard timeouts.
- Relying on resource monitors for total spend control while serverless features grow unmonitored.
- Untagged warehouses that make chargeback a manual exercise.

## Learn more

- [Warehouse considerations](https://docs.snowflake.com/en/user-guide/warehouses-considerations)
- [Multi-cluster warehouses](https://docs.snowflake.com/en/user-guide/warehouses-multicluster)
- [Understanding compute cost](https://docs.snowflake.com/en/user-guide/cost-understanding-compute)

## Knowledge check

### A company created one X-Small warehouse per analyst (120 warehouses). Costs are high despite low query volume. What is the best redesign?
- [ ] Increase auto-suspend on every warehouse
- [x] Consolidate analysts onto a shared multi-cluster ad hoc warehouse and use query-level attribution for chargeback
- [ ] Convert all warehouses to Snowpark-optimized
- [ ] Disable auto-resume
> Many tiny warehouses multiply minimum charges and idle tails; a shared auto-scaling warehouse uses compute more efficiently, and query attribution preserves per-user chargeback.

### Nightly MERGE jobs and morning dashboards share a warehouse, and dashboards slow down when jobs overrun. What is the primary fix?
- [ ] Lower the dashboard warehouse's auto-suspend
- [x] Move ETL and BI to separate warehouses sized and scaled for each workload
- [ ] Increase MAX_CONCURRENCY_LEVEL
- [ ] Add a resource monitor with SUSPEND_IMMEDIATE
> Separating workloads removes contention and lets ETL scale up while BI scales out independently.

### Which source allows you to attribute compute credits to individual users running on a shared warehouse?
- [ ] WAREHOUSE_METERING_HISTORY
- [x] QUERY_ATTRIBUTION_HISTORY
- [ ] RESOURCE_MONITORS
- [ ] METERING_DAILY_HISTORY
> QUERY_ATTRIBUTION_HISTORY attributes warehouse compute credits to individual queries, which can be aggregated by user or query tag.
