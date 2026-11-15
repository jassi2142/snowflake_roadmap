# Pruning & Clustering Keys

Pruning is how Snowflake avoids reading data it does not need: it skips whole micro-partitions whose metadata proves they cannot contain matching rows. Clustering keys help keep related rows together so pruning stays effective on very large tables, but they cost credits and storage, so they should be applied deliberately.

## How it works

**Pruning.** Every micro-partition stores metadata such as the minimum and maximum value of each column. When a query filters on a column, the optimizer compares the predicate to that metadata and skips partitions that cannot match. In the Query Profile, a TableScan shows *partitions scanned* versus *partitions total*; a small ratio means pruning is working.

Pruning depends on **how data is physically ordered**. Data loaded in date order is naturally well clustered by date, so date filters prune well. Over time, DML on very large tables can scatter values across many partitions, increasing overlap and **clustering depth**, and pruning degrades.

**Clustering keys.** A clustering key is one or more columns or expressions designated with `CLUSTER BY` to co-locate similar values. Once defined, **Automatic Clustering** reclusters the table in the background as needed, as a serverless service. Key points from the documentation:

- Clustering is best for tables with a large number of micro-partitions (typically multiple terabytes), where queries are selective or sort on the key, and many queries benefit from the same key.
- Snowflake recommends a maximum of **3 or 4 columns or expressions** per key.
- Order multi-column keys from **lowest to highest cardinality**.
- Avoid very low cardinality (a Boolean prunes little) and very high cardinality (raw nanosecond timestamps). Use an expression such as `TO_DATE(ts)` to reduce cardinality while preserving order.
- Keys cannot be defined directly on VARIANT, OBJECT, ARRAY or GEOGRAPHY columns, but you can cluster on a typed path expression such as `v:"id"::NUMBER`.
- Reclustering creates new micro-partitions; the old ones stay in Time Travel and Fail-safe, which increases storage.
- Snowflake has two Automatic Clustering versions: Clustering Classic and the newer Optima Clustering. `SYSTEM$CLUSTERING_INFORMATION` reports which a table uses, and the `VERSION` column of `AUTOMATIC_CLUSTERING_HISTORY` lets you compare costs.

## Example

Check how well a table is clustered on a candidate column (works with or without a defined key):

```sql
SELECT SYSTEM$CLUSTERING_INFORMATION('sales.public.orders', '(order_date)');
```

Define a key that reduces timestamp cardinality, then confirm it in SHOW TABLES:

```sql
ALTER TABLE sales.public.orders CLUSTER BY (TO_DATE(order_ts), region);

SHOW TABLES LIKE 'ORDERS' IN SCHEMA sales.public;
```

Monitor the credits Automatic Clustering consumes:

```sql
SELECT TO_DATE(start_time) AS day,
       table_name,
       SUM(credits_used)   AS credits
FROM snowflake.account_usage.automatic_clustering_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY credits DESC;
```

Suspend or resume reclustering, or remove the key:

```sql
ALTER TABLE sales.public.orders SUSPEND RECLUSTER;
ALTER TABLE sales.public.orders RESUME RECLUSTER;
ALTER TABLE sales.public.orders DROP CLUSTERING KEY;
```

## Best practices

- Baseline representative queries (time and partitions scanned) before adding a key, and measure again afterwards.
- Choose columns used in selective filters first, then join columns.
- Prefer tables with a high ratio of queries to DML; batch DML on clustered tables.
- Write filters directly on the clustered column or expression so the optimizer can use its metadata.
- Watch clustering credits for the first weeks after enabling a key.

## Common pitfalls

- Clustering small tables, which adds cost with little or no benefit.
- Clustering on a unique ID or high-precision timestamp, which is expensive to maintain.
- Wrapping the filter column in a function that does not match the key, which can prevent pruning.
- Forgetting that `CREATE TABLE ... CLONE` copies the key but leaves Automatic Clustering suspended on the clone.
- Expecting immediate results; reclustering runs only when Snowflake judges the table will benefit.

## Learn more

- [Clustering Keys & Clustered Tables](https://docs.snowflake.com/en/user-guide/tables-clustering-keys)
- [Automatic Clustering](https://docs.snowflake.com/en/user-guide/tables-auto-reclustering)

## Knowledge check

### A 5 TB fact table is queried mostly with filters on event timestamp (microsecond precision). Which clustering key is the best starting point?
- [ ] The raw event timestamp column
- [x] TO_DATE(event_timestamp)
- [ ] The unique event_id column
- [ ] A Boolean is_processed column
> Truncating the timestamp to a date preserves order for pruning while reducing cardinality, which makes clustering far cheaper to maintain.

### Which table is the weakest candidate for a clustering key?
- [ ] A multi-terabyte table queried hundreds of times per day on the same date column
- [ ] A large table whose clustering depth has grown and whose queries have slowed down
- [x] A 2 GB lookup table that is updated every few minutes
- [ ] A large table rarely updated but frequently filtered by region and date
> Small, frequently changing tables gain little from pruning improvements and incur continuous reclustering cost.

### You define a multi-column clustering key on (customer_id, region), where region has 5 values and customer_id has millions. What should you change?
- [ ] Nothing; higher cardinality columns should come first
- [x] Reorder to (region, customer_id), lowest to highest cardinality
- [ ] Add more columns to make the key unique
- [ ] Replace both with a VARIANT column
> Snowflake recommends ordering clustering key columns from lowest to highest cardinality; putting a high-cardinality column first reduces clustering effectiveness for the later column.
