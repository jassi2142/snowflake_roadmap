# Serverless Features

Serverless features are Snowflake capabilities that run on compute managed by Snowflake rather than on a virtual warehouse you create. Snowflake sizes and scales these resources automatically and bills only for the compute actually used, which changes how you monitor and control their cost.

## How it works

Snowflake compute costs fall into four categories: user-managed virtual warehouses, serverless compute, compute pools (for Snowpark Container Services), and cloud services. Serverless compute is automatically resized and scaled by Snowflake for each workload.

Billing model:

- Usage is measured in **compute-hours**, calculated per second and rounded up to the nearest whole second.
- The credits charged per compute-hour **vary by feature**; the rates are listed in the "Serverless Feature Credit Table" of the Snowflake Service Consumption Table.
- Each serverless feature appears as its own line item. Its Snowflake-managed compute and related cloud services appear together in that line item.
- Serverless compute does not count toward the daily 10% cloud services adjustment, which is calculated against warehouse usage only.

Features that use serverless compute include (service types as shown in `METERING_HISTORY`):

- Snowpipe (`PIPE`) and Snowpipe Streaming (`SNOWPIPE_STREAMING`)
- Automatic Clustering (`AUTO_CLUSTERING`)
- Materialized view maintenance (`MATERIALIZED_VIEW`)
- Search Optimization Service (`SEARCH_OPTIMIZATION`)
- Serverless tasks (`SERVERLESS_TASK`) and serverless alerts (`SERVERLESS_ALERTS`)
- Query Acceleration Service (`QUERY_ACCELERATION`)
- Replication (`REPLICATION`)
- Data quality monitoring (`DATA_QUALITY_MONITORING`)
- Cortex AI functions and related services (`AI_SERVICES`)

This list is not exhaustive; the `METERING_HISTORY` view documents many more service types.

Cost control differs from warehouses. **Resource monitors do not track or suspend serverless features**; they work for warehouses only. To monitor serverless spending, use **budgets**, and control each feature at its source (for example, suspend a task, pause a pipe, or remove a clustering key).

## Example

See serverless credits by service type over the last 30 days:

```sql
SELECT service_type,
       ROUND(SUM(credits_used), 2) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND service_type <> 'WAREHOUSE_METERING'
GROUP BY service_type
ORDER BY credits DESC;
```

Create a serverless task by omitting the `WAREHOUSE` parameter:

```sql
CREATE TASK refresh_daily_summary
  SCHEDULE = 'USING CRON 0 2 * * * UTC'
  AS
  INSERT INTO daily_summary
  SELECT order_date, SUM(amount) FROM orders
  WHERE order_date = CURRENT_DATE - 1
  GROUP BY order_date;
```

Find which tables drive Automatic Clustering cost:

```sql
SELECT database_name, schema_name, table_name,
       SUM(credits_used) AS credits
FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
WHERE start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3
ORDER BY credits DESC
LIMIT 10;
```

## Best practices

- Review serverless spend monthly by service type; it is easy to overlook because no warehouse appears in the bill.
- Use budgets to alert on serverless and AI spending, since resource monitors cannot.
- Evaluate each feature's value: drop clustering keys, search optimization, or materialized views that queries no longer use.
- Prefer serverless tasks for short, frequent jobs that would otherwise keep a warehouse running for the 60-second minimum.
- Check the feature-specific credit rates in the consumption table when comparing serverless against warehouse-based approaches.

## Common pitfalls

- Assuming an account-level resource monitor caps all spend. It does not cover serverless features.
- Enabling Automatic Clustering or search optimization on high-churn tables and incurring continuous maintenance cost.
- Assuming serverless costs are the same rate as warehouse credits for equivalent work; rates vary by feature.
- Forgetting that some features, such as QAS on new Gen2 and multi-cluster warehouses, may be enabled by default.

## Learn more

- [Understanding compute cost](https://docs.snowflake.com/en/user-guide/cost-understanding-compute)
- [METERING_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/metering_history)
- [Working with resource monitors](https://docs.snowflake.com/en/user-guide/resource-monitors)

## Knowledge check

### Your account-level resource monitor shows plenty of headroom, yet the monthly bill is much higher than expected. What is a likely explanation?
- [ ] Resource monitors double-count warehouse credits
- [x] Serverless features such as Snowpipe or Automatic Clustering consumed credits that resource monitors do not track
- [ ] Cloud services are never billed
- [ ] Suspended warehouses still consume credits
> Resource monitors cover warehouses only; serverless feature usage must be monitored with budgets or usage views.

### How is serverless compute metered?
- [ ] Per hour, with a one-hour minimum
- [ ] Per query, at a flat rate
- [x] In compute-hours calculated per second, with a credit rate that varies by feature
- [ ] At the same per-hour rate as an X-Small warehouse
> Serverless usage is measured in compute-hours on a per-second basis, and each feature has its own credits-per-compute-hour rate.

### A job runs a 10-second statement every 5 minutes on a dedicated warehouse. Which change most directly reduces its idle-compute overhead?
- [ ] Increase the warehouse size
- [x] Convert it to a serverless task
- [ ] Add a resource monitor
- [ ] Enable multi-cluster
> Each warehouse resume bills at least 60 seconds, while serverless tasks bill only for compute actually used.
