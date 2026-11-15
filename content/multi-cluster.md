# Multi-cluster Warehouses

A multi-cluster warehouse is a warehouse that can run more than one cluster of the same size at the same time. It is Snowflake's mechanism for scaling **out** to handle many concurrent users and queries, as opposed to resizing, which scales **up** to make individual queries faster. Multi-cluster warehouses require Enterprise Edition or higher.

## How it works

A standard warehouse has one cluster. When it runs out of resources, extra queries queue. A multi-cluster warehouse is defined by `MIN_CLUSTER_COUNT` and `MAX_CLUSTER_COUNT`, and Snowflake routes queries across the running clusters.

There are two modes:

- **Maximized**: min equals max (and is greater than 1). All clusters start when the warehouse starts. Good for steady, predictable high concurrency.
- **Auto-scale**: min is less than max. Snowflake starts clusters as queries begin to queue and shuts them down as load drops.

In auto-scale mode, `SCALING_POLICY` controls how eagerly clusters are added:

- **STANDARD** (default): favors starting clusters to minimize queuing. A cluster starts when a query is queued or Snowflake estimates current clusters cannot absorb more work. Idle clusters are shut down after a sustained period of low load.
- **ECONOMY**: favors keeping running clusters fully loaded. A new cluster starts only if Snowflake estimates enough load to keep it busy for at least 6 minutes, so queries may queue longer.

The maximum cluster count depends on size: up to 300 for X-Small through Medium, 160 for Large, 80 for X-Large, 40 for 2X-Large, 20 for 3X-Large, and 10 for 4X-Large and above. Snowsight currently only lets you choose up to 10; higher values require SQL.

Billing is size multiplied by the number of clusters actually running, per second. A Medium warehouse (4 credits/hour on Gen1) with a max of 3 clusters can consume at most 12 credits per hour. Resizing applies to all clusters.

Auto-suspend and auto-resume apply to the whole warehouse: it suspends only when down to its minimum clusters and idle.

When you create a **new** multi-cluster warehouse, Snowflake enables the Query Acceleration Service by default with a max scale factor of 8. Converting an existing single-cluster warehouse to multi-cluster does not change its QAS setting.

## Example

Create an auto-scaling BI warehouse:

```sql
CREATE WAREHOUSE bi_wh
  WAREHOUSE_SIZE = 'SMALL'
  MIN_CLUSTER_COUNT = 1
  MAX_CLUSTER_COUNT = 4
  SCALING_POLICY = 'STANDARD'
  AUTO_SUSPEND = 300
  AUTO_RESUME = TRUE;
```

Switch to the Economy policy to reduce cost on a less latency-sensitive workload:

```sql
ALTER WAREHOUSE bi_wh SET SCALING_POLICY = 'ECONOMY';
```

Inspect cluster settings and how many clusters are running:

```sql
SHOW WAREHOUSES LIKE 'BI_WH'
  ->> SELECT "name", "min_cluster_count", "max_cluster_count", "started_clusters", "scaling_policy"
        FROM $1;
```

## Best practices

- Use auto-scale mode unless you have a specific need for Maximized.
- Keep minimum at 1 unless you need high availability; set maximum as high as your budget tolerates.
- Start with a small maximum (2 or 3), observe queuing, and adjust.
- Use multi-cluster for concurrency; resize for slow individual queries.
- Use STANDARD for user-facing workloads and consider ECONOMY for batch or tolerant workloads.

## Common pitfalls

- Expecting more clusters to speed up a single slow query. A query runs on one cluster.
- Setting min equal to max by accident, which runs all clusters whenever the warehouse is up.
- Forgetting that maximum credits equal size times max clusters, and not budgeting for it.
- Trying to use multi-cluster on Standard Edition, where it is not available.

## Learn more

- [Multi-cluster warehouses](https://docs.snowflake.com/en/user-guide/warehouses-multicluster)
- [Warehouse considerations](https://docs.snowflake.com/en/user-guide/warehouses-considerations)

## Knowledge check

### A nightly batch tolerates some queuing, and the team wants to minimize credit spend on extra clusters. Which configuration fits best?
- [ ] Maximized mode with 6 clusters
- [x] Auto-scale mode with SCALING_POLICY = 'ECONOMY'
- [ ] Auto-scale mode with SCALING_POLICY = 'STANDARD'
- [ ] A single 6X-Large cluster
> Economy only starts additional clusters when it expects enough work to keep them busy, trading some queuing for lower cost.

### A Medium multi-cluster warehouse (Gen1) has MIN_CLUSTER_COUNT = 2 and MAX_CLUSTER_COUNT = 5. What is the maximum credit consumption per hour?
- [ ] 8
- [ ] 10
- [x] 20
- [ ] 4
> Maximum hourly credits are the per-cluster rate (4 for Medium) multiplied by the maximum cluster count (5).

### A single large report query is slow on a multi-cluster warehouse. Which change most directly improves that query?
- [ ] Increase MAX_CLUSTER_COUNT
- [x] Increase the warehouse size
- [ ] Change the scaling policy to STANDARD
- [ ] Set MIN_CLUSTER_COUNT equal to MAX_CLUSTER_COUNT
> A query runs on one cluster, so more clusters help concurrency but not single-query speed; a larger size gives each cluster more resources.
