# Metadata & Cloud Services

The cloud services layer coordinates Snowflake. It handles authentication, access control, metadata, query compilation and optimization, and transactions. It also lets some operations finish without any virtual warehouse. If you understand what runs here, you can explain metadata-only queries, the impact of compilation time, and the cloud services line on your bill.

## How it works

**Responsibilities**

- **Metadata management.** Snowflake keeps metadata about objects and about every micro-partition, such as per-column value ranges and distinct counts. The optimizer uses this metadata to prune partitions. It also lets some queries, such as `COUNT(*)` on a table or `MIN`/`MAX` on certain columns, return results from metadata alone.
- **Parsing, compilation, and optimization.** Every query is parsed, checked against access control, and turned into an execution plan before it reaches a warehouse. Pruning decisions are made here. Very large SQL text, many joins or Cartesian products, and large IN-lists all raise compilation cost.
- **Metadata-only operations.** DDL, `SHOW` commands, and zero-copy cloning are metadata operations and use only cloud services resources.
- **Result cache.** Queries that can be answered from the result cache are served through cloud services rather than a warehouse.
- **Security and transactions.** Authentication, session management, and transaction coordination also run here.

**Billing: the daily 10% adjustment**

Cloud services usage is measured in credits. You are billed for it only when your daily cloud services usage is more than 10% of your daily warehouse compute usage. In the `SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY` view:

- `CREDITS_ADJUSTMENT_CLOUD_SERVICES` is a negative number that offsets cloud services usage up to 10% of compute.
- `CREDITS_USED + CREDITS_ADJUSTMENT_CLOUD_SERVICES = CREDITS_BILLED`.

The adjustment appears only in METERING_DAILY_HISTORY and on the usage statement. Views such as WAREHOUSE_METERING_HISTORY and QUERY_HISTORY (which has a per-query `CREDITS_USED_CLOUD_SERVICES` column) show unadjusted usage, so their totals will be higher than what you are billed.

**Patterns that drive cloud services usage**

- COPY commands with poor file selectivity (listing many files in cloud storage)
- High-frequency DDL or cloning
- Tens of thousands of tiny queries per day (for example `SELECT 1`)
- Frequent INFORMATION_SCHEMA queries or `SHOW` commands from tools
- Single-row inserts and schema-per-tenant designs that create a lot of metadata
- Very complex SQL with long compilation times

## Example

This query finds days when cloud services were actually billed after the adjustment:

```sql
SELECT usage_date,
       SUM(credits_used_compute)              AS compute,
       SUM(credits_used_cloud_services)       AS cloud_services,
       SUM(credits_adjustment_cloud_services) AS adjustment,
       SUM(credits_billed)                    AS billed
FROM snowflake.account_usage.metering_daily_history
WHERE usage_date >= DATEADD(day, -30, CURRENT_DATE())
GROUP BY usage_date
HAVING SUM(credits_used_cloud_services) + SUM(credits_adjustment_cloud_services) > 0
ORDER BY usage_date;
```

This query finds the statements that use the most cloud services credits:

```sql
SELECT query_type, warehouse_name,
       SUM(credits_used_cloud_services) AS cs_credits,
       COUNT(*) AS queries
FROM snowflake.account_usage.query_history
WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY cs_credits DESC
LIMIT 20;
```

## Best practices

- Use METERING_DAILY_HISTORY, not QUERY_HISTORY totals, to see how much cloud services you are actually billed for.
- Organize stage paths with prefixes (for example, by date) so COPY lists only the files it needs.
- Batch small inserts, and reduce polling queries and `SHOW` calls from applications and tools.
- Clone only the objects you need, at the frequency you need.

## Common pitfalls

- Treating unadjusted cloud services credits in QUERY_HISTORY as billed cost.
- Assuming a query that ran without a warehouse was free. Metadata work still counts toward cloud services usage.
- Schema-per-customer designs with row-by-row loading, which inflate metadata operations.

## Learn more

- [METERING_DAILY_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/metering_daily_history)
- [Exploring compute cost](https://docs.snowflake.com/en/user-guide/cost-exploring-compute)

## Knowledge check

### On one day an account uses 100 warehouse credits and 8 cloud services credits. How many cloud services credits are billed?
- [ ] 8
- [ ] 2
- [x] 0
- [ ] 10
> The daily adjustment covers cloud services usage up to 10% of compute (10 credits here), so 8 credits are fully offset.

### A partner BI tool sends tens of thousands of `SHOW` commands per day, and cloud services charges are rising. Why?
- [ ] SHOW commands need a large warehouse
- [x] SHOW commands are metadata operations that use only cloud services, and the high volume adds up
- [ ] SHOW commands bypass the 10% adjustment
- [ ] SHOW commands are billed as storage
> SHOW is entirely metadata work. At high frequency, its cloud services usage can exceed the 10% adjustment.

### Which view should you use to reconcile billed credits, including the cloud services adjustment?
- [ ] QUERY_HISTORY
- [ ] WAREHOUSE_METERING_HISTORY
- [x] METERING_DAILY_HISTORY
- [ ] TABLE_STORAGE_METRICS
> Only METERING_DAILY_HISTORY (and the usage statement) shows the adjustment and CREDITS_BILLED.
