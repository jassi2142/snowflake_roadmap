# Query Profile (operators, statistics, GET_QUERY_OPERATOR_STATS)

The Query Profile is Snowflake's execution-plan viewer: it shows the tree of operators a query actually ran, how long each one took, and how much data flowed between them. It is the first place to look when a query is slow or expensive, because it tells you *where* the time went instead of leaving you to guess.

## How it works

When a query finishes, Snowflake records per-operator statistics. You can view them in Snowsight (open a query from **Monitoring » Query History** and select the **Query Profile** tab) or read them programmatically with the `GET_QUERY_OPERATOR_STATS` table function.

The profile is a tree of **operators**. Common ones include:

- **TableScan** – reads a table; shows partitions scanned vs. total and bytes scanned.
- **Filter** – applies a predicate; shows the filter condition.
- **Join** / **CartesianJoin** – combines inputs; shows the join condition and join type.
- **JoinFilter** – removes rows that cannot match a later join.
- **Aggregate**, **Sort**, **SortWithLimit**, **WindowFunction** – grouping, ordering and analytic work.
- **Result** – returns rows to the client.

For each operator you get:

- **Execution time breakdown** – percentage of total time spent on processing (CPU), local disk I/O, remote disk I/O, network communication, synchronization and initialization.
- **Statistics** – input and output rows, bytes scanned, percentage scanned from cache, partitions scanned/total, and bytes spilled to local or remote storage.
- **Attributes** – operator-specific details such as the filter expression, join condition or list of scanned columns.

`GET_QUERY_OPERATOR_STATS(<query_id>)` returns one row per operator with the columns `QUERY_ID`, `STEP_ID`, `OPERATOR_ID`, `PARENT_OPERATORS`, `OPERATOR_TYPE`, `OPERATOR_STATISTICS`, `EXECUTION_TIME_BREAKDOWN` and `OPERATOR_ATTRIBUTES` (the last three are VARIANT objects). Key facts:

- It works only for **completed** queries executed in the **past 14 days**.
- You need **OPERATE or MONITOR** on the warehouse that ran the query.
- It is a table function, so wrap it in `TABLE()` in the FROM clause.

## Example

Run a query, capture its ID, then list the operators sorted by their share of total time:

```sql
SELECT o.o_orderpriority, COUNT(*)
FROM snowflake_sample_data.tpch_sf1.orders o
JOIN snowflake_sample_data.tpch_sf1.lineitem l ON l.l_orderkey = o.o_orderkey
GROUP BY 1;

SET qid = LAST_QUERY_ID();

SELECT operator_id,
       operator_type,
       execution_time_breakdown:overall_percentage::FLOAT AS pct_of_time,
       operator_statistics:input_rows::NUMBER              AS input_rows,
       operator_statistics:output_rows::NUMBER             AS output_rows,
       operator_statistics:pruning:partitions_scanned::NUMBER AS parts_scanned,
       operator_statistics:pruning:partitions_total::NUMBER   AS parts_total
FROM TABLE(GET_QUERY_OPERATOR_STATS($qid))
ORDER BY pct_of_time DESC NULLS LAST;
```

Detect "exploding" joins, where a join emits far more rows than it receives:

```sql
SELECT operator_id,
       operator_attributes:equality_join_condition::STRING AS join_cond,
       operator_statistics:output_rows / NULLIF(operator_statistics:input_rows, 0) AS row_multiple
FROM TABLE(GET_QUERY_OPERATOR_STATS($qid))
WHERE operator_type = 'Join'
ORDER BY row_multiple DESC;
```

## Best practices

- Start with the operator that has the highest `overall_percentage`; optimizing anything else rarely helps.
- Compare **partitions scanned vs. partitions total** on each TableScan to judge pruning.
- Check output rows on joins against their inputs to catch missing or wrong join keys.
- Look for non-zero spilling statistics; remote spilling in particular signals a memory problem.
- Save operator stats to a table for important recurring queries so you can compare before and after a change.

## Common pitfalls

- Reading total elapsed time only. A query can be slow because it was queued, not because the plan is bad; check queuing columns in QUERY_HISTORY as well.
- Expecting identical statistics on every run. Cache state, warehouse size, clustering and data volume all change the numbers.
- Calling the function on a running query or one older than 14 days; it returns no data.
- Forgetting that a query served from the result cache has almost no profile to analyze.

## Learn more

- [GET_QUERY_OPERATOR_STATS](https://docs.snowflake.com/en/sql-reference/functions/get_query_operator_stats)
- [Monitor query activity with Query History](https://docs.snowflake.com/en/user-guide/ui-snowsight-activity)

## Knowledge check

### A Join operator shows 2 million input rows and 900 million output rows. What is the most likely issue?
- [ ] The warehouse is too small
- [x] The join condition is incomplete or wrong, causing row explosion
- [ ] The table is not clustered
- [ ] The result cache was bypassed
> Output rows vastly exceeding input rows on a join is the classic sign of an exploding (near-Cartesian) join, usually from a missing or non-unique join key.

### You want to analyze operator statistics for a query that ran 20 days ago. What happens with GET_QUERY_OPERATOR_STATS?
- [ ] It returns the statistics normally
- [ ] It returns statistics only if you have ACCOUNTADMIN
- [x] It cannot return statistics because the function covers only the past 14 days
- [ ] It returns estimated statistics
> GET_QUERY_OPERATOR_STATS works only for completed queries executed in the past 14 days.

### A TableScan shows partitions scanned equal to partitions total on a large table, while the query filters on one day. What does this suggest?
- [ ] The query is spilling to remote storage
- [x] Pruning is ineffective for that filter, so the whole table is being read
- [ ] The query used the result cache
- [ ] The join order is wrong
> Scanning all partitions despite a selective filter means micro-partition metadata could not eliminate data, pointing to poor clustering or a predicate that blocks pruning.
