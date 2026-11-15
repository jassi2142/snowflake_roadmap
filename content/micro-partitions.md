# Micro-partitions

Snowflake automatically divides all table data into micro-partitions. These are small, contiguous units of storage that hold data in a compressed, columnar format. You never create or manage them yourself, but they are the main reason Snowflake can skip most of a large table when it answers a query.

## How it works

- **Size.** Each micro-partition holds between 50 MB and 500 MB of uncompressed data. The stored size is smaller because data is always compressed.
- **Automatic creation.** As rows are inserted or loaded, Snowflake groups them into micro-partitions in the order the data arrives. You do not write any DDL to define partitions, unlike traditional static partitioning.
- **Columnar storage.** Inside a micro-partition, each column is stored and compressed separately. Snowflake picks the most efficient compression for each column. A query reads only the columns it references.
- **Metadata.** For every micro-partition, Snowflake records metadata such as the range of values (minimum and maximum) for each column and the number of distinct values.
- **Pruning.** At query time, Snowflake compares your filter against this metadata and skips micro-partitions that cannot contain matching rows. This is called **pruning**. Ideally, a query that selects 10% of a value range scans only about 10% of the micro-partitions.
- **Immutability and DML.** Micro-partitions are never changed in place. Updates and deletes write new micro-partitions. Some operations, such as deleting all rows from a table, are metadata-only.

**Clustering** describes how well the order of the data matches the columns you filter on. If a table is loaded by date and you filter by date, each micro-partition covers a narrow date range, and pruning works well. Snowflake tracks **clustering depth**, the average depth of overlapping micro-partitions for given columns. An empty table has a depth of 0; lower values mean better clustering. For very large tables where natural ordering is poor, you can define a **clustering key**.

Not every filter can prune. For example, Snowflake does not prune based on a predicate that contains a subquery, even if the subquery returns a constant.

## Example

This checks how well a table is clustered on a column you often filter by:

```sql
SELECT SYSTEM$CLUSTERING_INFORMATION('sales', '(order_date)');
```

A selective filter on a well-clustered column lets Snowflake prune micro-partitions. After you run it, look at "Partitions scanned" versus "Partitions total" in the Query Profile.

```sql
SELECT SUM(amount)
FROM sales
WHERE order_date = '2026-10-01';
```

## Best practices

- Load data in a natural order (often by date) so micro-partitions cover narrow ranges of the columns you filter on.
- Filter on columns directly with simple predicates, such as `order_date >= '2026-01-01'`, so pruning can work.
- Select only the columns you need; columnar storage means fewer columns means less data scanned.
- Use the Query Profile to compare partitions scanned with partitions total.

## Common pitfalls

- Adding clustering keys to small tables, or to tables where queries already prune well. Clustering has ongoing maintenance costs.
- Wrapping filter columns in functions or subqueries, which can block pruning.
- Thinking you need to create or manage partitions yourself, as in other databases.

## Learn more

- [Micro-partitions & data clustering](https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions)
- [SYSTEM$CLUSTERING_DEPTH](https://docs.snowflake.com/en/sql-reference/functions/system_clustering_depth)

## Knowledge check

### How much uncompressed data does a single micro-partition typically contain?
- [ ] 1 MB to 10 MB
- [x] 50 MB to 500 MB
- [ ] 1 GB to 5 GB
- [ ] Exactly 16 MB
> Micro-partitions hold 50 MB to 500 MB of uncompressed data, stored compressed.

### A query filters on `event_date`, but the Query Profile shows it scanning almost every micro-partition. What is the most likely cause?
- [ ] The warehouse is too small
- [x] Rows for each date are spread across many micro-partitions, so the date ranges overlap heavily
- [ ] Micro-partitions are not enabled on the table
- [ ] The table has too many columns
> Pruning depends on narrow per-partition value ranges. Heavy overlap (poor clustering) forces Snowflake to scan more partitions.

### What does Snowflake use to decide which micro-partitions to skip?
- [ ] Secondary indexes created by the user
- [x] Per-partition metadata such as each column's minimum and maximum values
- [ ] A full scan of every partition
- [ ] The result cache
> Snowflake compares query predicates with stored per-partition metadata, such as value ranges, to prune partitions.
