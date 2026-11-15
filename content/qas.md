# Query Acceleration Service

The Query Acceleration Service (QAS) offloads parts of eligible queries to shared, serverless compute so that a warehouse can absorb outlier queries without being upsized. It is an Enterprise Edition feature, and for architects it is mainly a tool for handling skewed, unpredictable workloads where sizing the warehouse for the worst query would waste credits on every other query.

## How it works

When QAS is enabled on a warehouse, Snowflake can lease additional compute from a shared pool and push down parallelizable fragments of a query plan, mainly scanning and filtering, to that pool. Eligible patterns are:

- Large scans with an aggregation or selective filter.
- Large scans that insert or copy many new rows (for example, INSERT ... SELECT and COPY).

There is no fixed scan-size threshold. Snowflake marks a query eligible only when it has high confidence acceleration would help, based on the plan and warehouse size. Common ineligibility reasons:

- Too few partitions in the scan, so resource acquisition latency outweighs the benefit (`NO_LARGE_ENOUGH_SCAN`).
- Filters not selective enough, or GROUP BY cardinality too high.
- Certain LIMIT patterns, which QAS evaluates automatically.
- Nondeterministic functions such as SEQ or RANDOM.

**Scale factor** is the cost governor. `QUERY_ACCELERATION_MAX_SCALE_FACTOR` caps leased compute as a multiple of the warehouse size: a Medium (4 credits/hour on Gen1) with scale factor 5 can lease up to 20 extra credits per hour. The default is 8; 0 removes the cap. The factor applies to the warehouse as a whole, including multi-cluster warehouses, so consider raising it there. The service only uses what each query needs and what is available, so performance gains can fluctuate.

**Billing**: QAS credits are serverless, billed per second only while in use, and separate from warehouse credits. The cost does not depend on how many queries use the service concurrently.

**Defaults**: QAS is enabled by default on newly created Gen2 standard warehouses and newly created multi-cluster warehouses (scale factor 8). Converting an existing warehouse does not change its QAS state.

**Interactions**: Search optimization can prune micro-partitions first, after which QAS can offload remaining eligible work. When QAS is enabled, Snowflake writes small amounts of data to remote storage for eligible queries, so nonzero `bytes_spilled_to_remote_storage` is expected.

## Example

Find warehouses with the most eligible acceleration time last week:

```sql
SELECT warehouse_name,
       SUM(eligible_query_acceleration_time) AS total_eligible_time
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
WHERE start_time > DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name
ORDER BY total_eligible_time DESC;
```

Estimate the benefit for one query at different scale factors:

```sql
SELECT PARSE_JSON(SYSTEM$ESTIMATE_QUERY_ACCELERATION('<query_id>'));
```

Enable QAS with a bounded scale factor:

```sql
ALTER WAREHOUSE adhoc_wh SET
  ENABLE_QUERY_ACCELERATION = TRUE
  QUERY_ACCELERATION_MAX_SCALE_FACTOR = 4;
```

Measure QAS spend month to date:

```sql
SELECT warehouse_name, SUM(credits_used) AS qas_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY
WHERE start_time >= DATE_TRUNC(month, CURRENT_DATE)
GROUP BY 1
ORDER BY 2 DESC;
```

## Best practices

- Target warehouses with mixed workloads and occasional heavy scans, such as ad hoc analytics, rather than uniformly heavy ETL.
- Use `upper_limit_scale_factor` distribution in QUERY_ACCELERATION_ELIGIBLE to pick a scale factor instead of defaulting to 0.
- Compare combined warehouse plus QAS credits before and after, with a stable workload, using WAREHOUSE_METERING_HISTORY and QUERY_ACCELERATION_HISTORY.
- Consider downsizing a warehouse after enabling QAS if it was sized for outliers.
- Decide explicitly whether new Gen2 and multi-cluster warehouses should keep the default QAS setting.

## Common pitfalls

- Expecting QAS to fix joins, high-cardinality aggregations, or short queries; these are often ineligible.
- Setting scale factor 0 on a large warehouse without a budget, allowing unbounded serverless spend.
- Forgetting that QAS credits are not covered by resource monitors.
- Misreading remote spill metrics as a problem when QAS is enabled.

## Learn more

- [Using the Query Acceleration Service (QAS)](https://docs.snowflake.com/en/user-guide/query-acceleration-service)
- [SYSTEM$ESTIMATE_QUERY_ACCELERATION](https://docs.snowflake.com/en/sql-reference/functions/system_estimate_query_acceleration)

## Knowledge check

### An ad hoc warehouse is sized 2X-Large only because a few weekly queries scan billions of rows with selective filters; most queries are small. What is the most cost-effective design?
- [ ] Keep 2X-Large and add more clusters
- [x] Downsize the warehouse and enable QAS with a bounded scale factor
- [ ] Move all queries to a Snowpark-optimized warehouse
- [ ] Lower MAX_CONCURRENCY_LEVEL to 1
> QAS supplies extra compute only to eligible outlier scans, so the base warehouse can be sized for the typical query.

### A Large Gen1 warehouse (8 credits/hour) has QUERY_ACCELERATION_MAX_SCALE_FACTOR = 3. What is the maximum additional QAS consumption rate?
- [ ] 3 credits per hour
- [ ] 8 credits per hour
- [x] 24 credits per hour
- [ ] Unlimited
> The scale factor multiplies the warehouse's rate, so leased compute can reach 3 x 8 = 24 credits per hour on top of the warehouse.

### SYSTEM$ESTIMATE_QUERY_ACCELERATION returns status ineligible with reason NO_LARGE_ENOUGH_SCAN. What does that indicate?
- [ ] QAS is disabled on the warehouse
- [x] The query does not scan enough partitions for acceleration to outweigh its overhead
- [ ] The scale factor is too low
- [ ] The query uses a nondeterministic function
> When too few partitions are scanned, the latency of acquiring QAS resources cancels out the benefit, so the query is ineligible.
