# Hybrid Tables (Unistore)

Hybrid tables are a Snowflake table type that is backed by a row store, with enforced primary key, unique, and foreign key constraints, row-level locking, and synchronously maintained indexes. They target low-latency, high-concurrency point reads and writes (application state, workflow metadata, serving precomputed results) while staying joinable with standard tables in the same query engine. That is the core of Snowflake's Unistore proposition.

## How it works

Writes go directly to a row store, which is the primary storage. Data is copied asynchronously to object storage, so large analytical scans can be served from columnar storage without disturbing the operational workload. The optimizer decides where to read from. Hybrid tables use the same warehouses, governance, and SQL as everything else, and a single transaction can span hybrid and standard tables.

Design-relevant properties:

- **Constraints**: a `PRIMARY KEY` is required and enforced. `UNIQUE`, `FOREIGN KEY`, and `NOT NULL` are enforced. `CHECK` constraints are enforced but can only be defined when the table is created. You cannot mark these constraints `NOT ENFORCED`. Data is ordered by the primary key, and clustering keys are not supported.
- **Indexes**: secondary indexes are maintained synchronously on write. You cannot alter an index or add columns to it, so you drop and recreate it instead. Geospatial, semi-structured, and VECTOR columns cannot be indexed. TIMESTAMP_TZ is not allowed in primary key, unique, or foreign key columns.
- **Consistency**: session-based by default, with possible staleness under 100 ms for writes made from other sessions. `READ_LATEST_WRITES = TRUE` removes the staleness at a small latency cost.
- **Transactions**: the transaction scope is one database. All hybrid tables in a transaction must be in the same database.
- **Quotas**: 2 TB of active hybrid data per database, throttled request rates of roughly 16,000 operations per second per database for a balanced 80/20 read/write workload, and at most 200 databases containing hybrid tables per account. Support can adjust some quotas.
- **Availability**: generally available in AWS and Azure commercial regions, Preview on Google Cloud, and not available in trial accounts or U.S. SnowGov regions. Tri-Secret Secure accounts require Dedicated Storage Mode.

Not supported today: clustering keys, data sharing, dynamic tables, Fail-safe, materialized views, the Query Acceleration Service, replication, the Search Optimization Service, Snowpipe and Snowpipe Streaming, streams, UNDROP, temporary or transient hybrid tables, and table-level or schema-level cloning. Time Travel is limited to `AT(TIMESTAMP => ...)`. Queries do not use the result cache. The higher-order functions FILTER, REDUCE, and TRANSFORM are not supported in queries against hybrid tables.

Storage costs are higher than for standard tables because row-oriented data compresses less well.

## Example

An order-state table with enforced integrity and a secondary index for status lookups:

```sql
CREATE HYBRID TABLE app.ops.customers (
  customer_id NUMBER PRIMARY KEY,
  email       VARCHAR NOT NULL UNIQUE,
  name        VARCHAR
);

CREATE HYBRID TABLE app.ops.orders (
  order_id    NUMBER PRIMARY KEY,
  customer_id NUMBER NOT NULL REFERENCES app.ops.customers (customer_id),
  status      VARCHAR NOT NULL,
  updated_at  TIMESTAMP_NTZ,
  INDEX idx_status (status)
);
```

A point update and a lookup that the row store serves with low latency:

```sql
UPDATE app.ops.orders
SET status = 'SHIPPED', updated_at = CURRENT_TIMESTAMP()
WHERE order_id = 1001;

SELECT order_id, status FROM app.ops.orders WHERE order_id = 1001;
```

An application would run these through a driver with bind variables rather than Snowsight, whose interactive overhead is not representative of hybrid table latency.

## Best practices

- Use hybrid tables for the operational slice only (state, entities accessed by key, serving tables) and keep large fact data in standard tables. Join them as needed.
- Design primary keys and secondary indexes around the actual access paths, because queries that cannot use an index scan more and count against throttling.
- Load in bulk with `CREATE HYBRID TABLE ... AS SELECT` or INSERT from a staged dataset, and use INSERT, UPDATE, and DELETE rather than MERGE for small row-level changes.
- Use a dedicated, appropriately sized warehouse with multi-cluster scaling for concurrent application traffic, and measure latency from the application's driver.
- Plan around the per-database quotas: spread independent applications across databases, and monitor throttling in `AGGREGATE_QUERY_HISTORY`.
- Design disaster recovery explicitly, because hybrid tables are not replicated and have no Fail-safe.

## Common pitfalls

- Treating hybrid tables as a general replacement for standard tables and then losing replication, sharing, streams, and dynamic tables.
- Expecting `UNDROP` or table-level `CLONE` to work for recovery or environment copies.
- Spreading one transaction's tables across databases, which fails because the transaction scope is a single database.
- Defining a CHECK constraint and later trying to load the table with COPY INTO, which is not allowed.
- Benchmarking in Snowsight and concluding that hybrid tables are slow.

## Learn more

- [Hybrid tables](https://docs.snowflake.com/en/user-guide/tables-hybrid)
- [Limitations and unsupported features for hybrid tables](https://docs.snowflake.com/en/user-guide/tables-hybrid-limitations)
- [CREATE HYBRID TABLE](https://docs.snowflake.com/en/sql-reference/sql/create-hybrid-table)

## Knowledge check

### A team wants to feed a hybrid table into a dynamic table pipeline and replicate it to a DR region. What should the architect tell them?
- [ ] Both work if change tracking is enabled
- [x] Hybrid tables do not support dynamic tables, streams, or replication, so the design needs another change-capture and recovery approach
- [ ] Only replication requires Business Critical Edition
- [ ] Use a materialized view over the hybrid table instead
> Dynamic tables, streams, replication, and materialized views are all unsupported for hybrid tables, which shapes pipeline and DR design.

### An ingestion framework uses thousands of parallel workers that each update one status row by key. Which table type and design fits?
- [x] A hybrid table keyed on the work item ID, with row-level locking and point updates
- [ ] A standard table clustered on the work item ID
- [ ] A transient table with search optimization
- [ ] An Iceberg table with frequent compaction
> High-concurrency single-row updates by key are the primary use case for hybrid tables, which lock rows rather than micro-partitions.

### A transaction updates a hybrid table in database APP and another hybrid table in database AUDIT. What happens?
- [ ] It succeeds with two-phase commit
- [ ] It succeeds but loses atomicity
- [x] It is not allowed, because all hybrid tables in a transaction must be in the same database
- [ ] It succeeds only with READ_LATEST_WRITES enabled
> The transaction scope for hybrid tables is the database, so co-locate tables that must be updated atomically. Standard tables in the same transaction can be in other databases.
