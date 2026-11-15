# Search Optimization Service

The Search Optimization Service (SOS) builds and maintains a persistent search access path on a table so that highly selective lookups can skip most micro-partitions, even when the filtered column is not the clustering key. It is a targeted accelerator for needle-in-a-haystack queries, priced as a serverless service plus additional storage, and it requires **Enterprise Edition or higher**.

## How it works

Standard pruning relies on per-partition min/max metadata, which only helps when values are physically co-located. SOS adds a separate data structure, the **search access path**, that records which micro-partitions contain which values. At query time the optimizer consults it to eliminate partitions that min/max metadata alone cannot.

Supported search methods are configured per column:

- **`EQUALITY`** – point lookups with `=` and `IN`, including on VARIANT paths and scalar functions in equality predicates.
- **`SUBSTRING`** – `LIKE`, `ILIKE`, `CONTAINS`, `STARTSWITH`, `ENDSWITH`, `RLIKE`/`REGEXP` and related predicates. The searched substring must be **five or more characters** for the access path to be used.

`ALTER TABLE t ADD SEARCH OPTIMIZATION` without `ON` enables EQUALITY for all columns of supported types (excluding semi-structured and GEOGRAPHY). Snowflake recommends enabling specific columns instead.

**When it pays off.** Documentation guidance for good candidates:

- The query runs for a few seconds or longer before optimization; sub-second queries rarely improve.
- At least one filtered column has on the order of 100,000 or more distinct values.
- The query is selective and returns few rows.
- The filter is on columns other than the primary clustering key.

**Cost model.**

- *Storage*: the access path is typically about one quarter of the table size and can approach the table size in extreme high-cardinality cases.
- *Compute*: an initial build (which can be massively parallel on large tables, causing a short cost spike) and ongoing maintenance roughly proportional to data added or changed. Automatic Clustering on the same table can raise SOS maintenance cost when churn is high.
- `SYSTEM$ESTIMATE_SEARCH_OPTIMIZATION_COSTS` returns best-effort estimates that may differ from actual cost by up to 50%, occasionally more.

**SOS vs. alternatives.** Clustering optimizes one dominant access pattern and benefits range scans; SOS serves many selective lookups on different columns without reordering data. Materialized views precompute a specific query shape. Query Acceleration offloads large scans to serverless compute but does not reduce partitions read. Architects often combine clustering on date with SOS on high-cardinality identifiers.

## Example

Estimate cost before enabling, then enable only the columns your workload filters on:

```sql
SELECT SYSTEM$ESTIMATE_SEARCH_OPTIMIZATION_COSTS(
  'security.logs.auth_events',
  'EQUALITY(user_id, session_id), SUBSTRING(user_agent)');

ALTER TABLE security.logs.auth_events
  ADD SEARCH OPTIMIZATION ON EQUALITY(user_id, session_id), SUBSTRING(user_agent);

DESCRIBE SEARCH OPTIMIZATION ON security.logs.auth_events;
```

Check build progress with `SHOW TABLES` (the `search_optimization_progress` column), then track maintenance credits:

```sql
SELECT TO_DATE(start_time) AS day,
       table_name,
       SUM(credits_used) AS credits
FROM snowflake.account_usage.search_optimization_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY credits DESC;
```

Remove a method that is not paying for itself:

```sql
ALTER TABLE security.logs.auth_events DROP SEARCH OPTIMIZATION ON SUBSTRING(user_agent);
```

## Best practices

- Derive candidate columns from workload analysis of real predicates, not from schema inspection.
- Start with a few tables and monitor cost and benefit closely, as Snowflake recommends.
- Batch DML on optimized tables; frequent small changes drive maintenance cost.
- If you plan to recluster an entire table, consider dropping search optimization first and re-adding it afterward.
- Verify use in the Query Profile: optimized scans show a search optimization access step and partitions pruned by search optimization.

## Common pitfalls

- Enabling SOS on the whole table by default and paying to index columns that are never filtered.
- Expecting gains for short substrings such as `LIKE '%abc%'`; fewer than five characters cannot use the access path.
- Using it for low-cardinality columns or queries that return a large fraction of the table.
- Querying before the build completes and concluding SOS does not work.
- Ignoring the combined maintenance cost of SOS plus Automatic Clustering on high-churn tables.

## Learn more

- [Search optimization service](https://docs.snowflake.com/en/user-guide/search-optimization-service)
- [Search optimization cost estimation and management](https://docs.snowflake.com/en/user-guide/search-optimization/cost-estimation)
- [Identifying queries that can benefit from search optimization](https://docs.snowflake.com/en/user-guide/search-optimization/queries-that-benefit)

## Knowledge check

### A 20 TB log table is clustered by event_date. Investigators run ad hoc lookups by request_id (unique per row) that take minutes and return a handful of rows. What is the best option?
- [ ] Change the clustering key to request_id
- [x] Add search optimization ON EQUALITY(request_id)
- [ ] Create a materialized view per investigator
- [ ] Increase the warehouse size to 4X-Large
> SOS targets selective point lookups on high-cardinality columns that are not the clustering key, without disturbing the date clustering that other queries rely on.

### Which query is least likely to benefit from SUBSTRING search optimization on a message column?
- [ ] WHERE message LIKE '%timeout exceeded%'
- [ ] WHERE CONTAINS(message, 'connection refused')
- [x] WHERE message LIKE '%err%'
- [ ] WHERE message RLIKE '.*(deadlock)+.*'
> Search access paths are used only for substrings of five or more characters, so a three-character pattern cannot benefit.

### A team enabled SOS and Automatic Clustering on a table receiving continuous MERGE traffic, and serverless costs spiked. What is the most appropriate first step?
- [ ] Disable Time Travel on the table
- [x] Review SEARCH_OPTIMIZATION_HISTORY and clustering credits, batch the DML, and limit SOS to the columns that are actually queried
- [ ] Switch the table to transient
- [ ] Add more columns to search optimization so it is used more often
> Maintenance cost is driven by churn and the number of optimized columns, and clustering on a high-churn table can amplify SOS maintenance; batching DML and narrowing scope address both drivers.
