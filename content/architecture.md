# Three-Layer Architecture

Snowflake's architecture has three layers: database storage, query processing (compute), and cloud services. Each layer scales on its own. Understanding how they fit together explains most of Snowflake's behavior, from why you can resize compute instantly to why some queries never use a warehouse.

## How it works

Snowflake combines ideas from two classic designs. Like a **shared-disk** system, it keeps all data in one central repository that every compute node can reach. Like a **shared-nothing** system, it processes queries on compute clusters where each node stores part of the data locally. You get the simple data management of shared-disk with the performance and scale-out of shared-nothing.

**1. Database storage**

When you load data, Snowflake reorganizes it into its internal compressed, columnar format and stores it in cloud object storage. Snowflake manages every aspect of this storage: file size, structure, compression, and metadata. You cannot see or access the underlying files directly; you reach the data only through SQL.

**2. Query processing (virtual warehouses)**

Queries run on **virtual warehouses**. A virtual warehouse is a cluster of compute resources that Snowflake provisions from the cloud provider. Each warehouse is independent and shares no compute with other warehouses, so one workload cannot slow down another. You can:

- Resize a warehouse to make complex queries faster.
- Suspend it when idle (no compute charges) and resume it when needed.
- Use multi-cluster warehouses (Enterprise Edition or higher) to add clusters automatically when many users run queries at once.

**3. Cloud services**

This layer coordinates the whole system. It handles authentication and access control, infrastructure management, metadata management, query parsing and optimization, and transaction management. It runs on compute that Snowflake manages, not on your warehouses.

Because the layers are separate, you can scale compute without moving data, scale storage without buying more compute, and run many workloads against one copy of the data.

## Example

The statements below touch each layer.

```sql
-- Cloud services: a metadata-only operation, no warehouse required
SHOW TABLES IN SCHEMA snowflake_sample_data.tpch_sf1;

-- Compute: resize a warehouse for a heavy job, then scale back down
ALTER WAREHOUSE learn_wh SET WAREHOUSE_SIZE = 'MEDIUM';

SELECT l_returnflag, SUM(l_extendedprice) AS revenue
FROM snowflake_sample_data.tpch_sf1.lineitem   -- Storage: shared central data
GROUP BY l_returnflag;

ALTER WAREHOUSE learn_wh SET WAREHOUSE_SIZE = 'XSMALL';
```

Resizing the warehouse changes compute capacity only; the stored table is untouched.

## Best practices

- Separate workloads such as ETL, BI, and data science onto different warehouses to isolate performance and track costs.
- Resize up for large, complex queries; use multi-cluster warehouses for many concurrent users.
- Let warehouses auto-suspend. Storage stays available even when no compute is running.

## Common pitfalls

- Thinking a larger warehouse fixes concurrency. Resizing helps individual query speed; concurrency is handled by adding clusters.
- Assuming data lives "inside" a warehouse. Warehouses hold only temporary cache; all persistent data is in the storage layer.
- Forgetting that the cloud services layer also does work (compilation, metadata operations) that can appear on your bill.

## Learn more

- [Key concepts & architecture](https://docs.snowflake.com/en/user-guide/intro-key-concepts)

## Knowledge check

### You suspend every virtual warehouse in an account. What happens to the data in your tables?
- [ ] It is deleted after the auto-suspend period
- [x] It stays in the storage layer and is available as soon as a warehouse resumes
- [ ] It moves to Fail-safe
- [ ] It becomes read-only until you contact support
> Storage is independent of compute, so suspending warehouses has no effect on stored data.

### Which layer parses and optimizes your SQL before it runs?
- [ ] Database storage
- [ ] Virtual warehouses
- [x] Cloud services
- [ ] The client driver
> The cloud services layer handles parsing, optimization, metadata, security, and transaction management.

### Fifty analysts run small dashboard queries at the same time and requests start queuing. What is the most appropriate fix?
- [ ] Increase the warehouse size to 4X-Large
- [x] Use a multi-cluster warehouse so more clusters start under load
- [ ] Move the data to a different database
- [ ] Add a clustering key to every table
> Queuing from many concurrent users is a concurrency problem, which multi-cluster warehouses handle by adding clusters.
