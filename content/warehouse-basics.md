# Warehouse Sizing

A virtual warehouse is the compute engine that runs your queries, loads data, and performs DML in Snowflake. Its size controls how much compute is available per cluster, and therefore both how fast heavy queries run and how many credits you burn per hour. Choosing a sensible size is one of the first and most impactful cost decisions you will make.

## How it works

Every warehouse has a **size** (X-Small through 6X-Large). Each step up roughly doubles the compute resources and doubles the credits billed per hour. For first-generation (Gen1) standard warehouses the hourly rates are:

| Size | Credits per hour |
| --- | --- |
| X-Small | 1 |
| Small | 2 |
| Medium | 4 |
| Large | 8 |
| X-Large | 16 |
| 2X-Large | 32 |
| 3X-Large | 64 |
| 4X-Large | 128 |
| 5X-Large | 256 |
| 6X-Large | 512 |

Key billing rules:

- Billing is **per second**, with a **60-second minimum** each time a warehouse starts or resumes. A warehouse that runs 30 seconds is billed for 60; one that runs 61 seconds is billed for 61.
- A suspended warehouse consumes no credits.
- X-Small is the default size when you run `CREATE WAREHOUSE` without specifying one.
- You can resize at any time, even while the warehouse is running. Queries already executing keep their original resources; queued and new queries use the new size once it is provisioned.

Because a query on a warehouse twice as large often finishes in roughly half the time, a larger warehouse can cost about the same for large, parallelizable queries while returning results sooner. This does not hold for small, simple queries, which cannot use the extra resources.

Each running warehouse also keeps a local cache of table data it has read. Larger warehouses have a larger cache. The cache is dropped when the warehouse suspends or when it is resized down.

Data loading is a special case: loading performance depends more on the number and size of files than on warehouse size. Unless you are loading hundreds or thousands of files concurrently, Small to Large is usually enough.

## Example

Create a small warehouse for a team, then resize it when a heavier workload arrives.

```sql
CREATE WAREHOUSE analytics_wh
  WAREHOUSE_SIZE = 'SMALL'
  AUTO_SUSPEND = 300
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- Temporarily scale up for a large monthly report
ALTER WAREHOUSE analytics_wh SET WAREHOUSE_SIZE = 'LARGE';

-- Scale back down afterwards
ALTER WAREHOUSE analytics_wh SET WAREHOUSE_SIZE = 'SMALL';
```

Use `SHOW WAREHOUSES` to check size and state:

```sql
SHOW WAREHOUSES LIKE 'ANALYTICS_WH';
```

## Best practices

- Start small and test: run representative queries (ones that take a few minutes) on two or three sizes and compare runtime and credits.
- Keep workloads of similar complexity on the same warehouse so its size can be tuned to that workload.
- Resize up for slow, complex queries; use multi-cluster warehouses (not bigger sizes) for many concurrent users.
- Pair every warehouse with auto-suspend so per-second billing actually saves money.
- Use a small warehouse for routine data loading unless you are loading very many files in parallel.

## Common pitfalls

- Assuming bigger is always faster. Simple lookups and small queries see little or no benefit from a larger size.
- Suspending and resuming repeatedly within a minute, which pays the 60-second minimum each time.
- Using one oversized warehouse for everything, which makes it impossible to right-size any single workload.
- Forgetting that resizing down drops part of the cache, so the next queries may be slower.

## Learn more

- [Overview of warehouses](https://docs.snowflake.com/en/user-guide/warehouses-overview)
- [Warehouse considerations](https://docs.snowflake.com/en/user-guide/warehouses-considerations)

## Knowledge check

### A Medium Gen1 warehouse runs continuously for 30 minutes. Roughly how many credits does it consume?
- [ ] 1
- [x] 2
- [ ] 4
- [ ] 8
> A Medium warehouse consumes 4 credits per hour, and per-second billing means 30 minutes costs about half of that, or 2 credits.

### A dashboard runs dozens of simple, fast queries and users complain about queuing at 9 AM. What is the most appropriate first change?
- [ ] Resize the warehouse from Small to 2X-Large
- [x] Add clusters (multi-cluster) rather than increasing size
- [ ] Disable auto-suspend
- [ ] Move the queries to a data loading warehouse
> Resizing mainly speeds up large, complex queries; concurrency problems with many small queries are better addressed by scaling out with more clusters.

### A warehouse resumes, runs a query for 20 seconds, and suspends. How long is it billed for?
- [ ] 20 seconds
- [x] 60 seconds
- [ ] 5 minutes
- [ ] One full hour
> Each start or resume incurs a 60-second minimum charge, after which billing is per second.
