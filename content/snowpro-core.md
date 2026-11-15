# SnowPro Core

SnowPro Core is Snowflake's foundational certification. It validates broad, practical knowledge of the Snowflake AI Data Cloud: architecture, security and access control, data loading and unloading, performance, data sharing, and data protection. It is the usual first step before the SnowPro Advanced role-based certifications.

## How it works

Exam details such as the current exam version, number of questions, duration, passing score, price, and domain weightings change over time. Always check the official exam guide on the Snowflake certification site before you study, and treat any figures you see elsewhere as potentially outdated.

The content areas the certification is known for map to core Snowflake concepts you should understand well:

- **Architecture**: the three layers (storage, virtual warehouse compute, and cloud services), micro-partitions, and how separation of storage and compute enables independent scaling. Editions (Standard, Enterprise, Business Critical, Virtual Private Snowflake) and which features need which edition.
- **Virtual warehouses**: sizes, auto-suspend and auto-resume, multi-cluster warehouses (Enterprise Edition or higher) for concurrency, and scaling up versus scaling out.
- **Account access and security**: role-based access control, system roles (ACCOUNTADMIN, SECURITYADMIN, USERADMIN, SYSADMIN, PUBLIC), role hierarchy, network policies, MFA, and key-pair authentication.
- **Data loading and unloading**: stages (user, table, named internal, external), file formats, `COPY INTO`, Snowpipe, and unloading with `COPY INTO <location>`.
- **Performance**: result cache, warehouse cache, pruning, clustering keys, Query Profile, and search optimization.
- **Data protection and sharing**: Time Travel, Fail-safe, zero-copy cloning, replication, and Secure Data Sharing.
- **Semi-structured data**: `VARIANT`, `FLATTEN`, and dot or bracket notation.

## Example

Hands-on practice is the most effective preparation. Work through common exam concepts in a trial account:

```sql
-- Warehouse behavior
CREATE WAREHOUSE study_wh WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

-- Loading from a stage
CREATE OR REPLACE FILE FORMAT csv_ff TYPE = CSV SKIP_HEADER = 1;
CREATE OR REPLACE STAGE study_stage FILE_FORMAT = csv_ff;
-- PUT file://orders.csv @study_stage;   (run from SnowSQL or Snowflake CLI)
COPY INTO orders FROM @study_stage;

-- Time Travel and cloning
SELECT * FROM orders AT (OFFSET => -300);
CREATE TABLE orders_backup CLONE orders;

-- Semi-structured data
SELECT f.value:sku::STRING AS sku
FROM raw_events, LATERAL FLATTEN(input => payload:items) f;
```

## Best practices

- Start from the official exam guide and map each domain to Snowflake documentation pages.
- Practice in a trial account; run each feature rather than only reading about it.
- Learn the "why" behind features (for example, why scaling out helps concurrency but not a single slow query).
- Track which features require Enterprise or Business Critical Edition.
- Use Snowflake's official learning resources and practice materials where available.

## Common pitfalls

- Studying from outdated third-party dumps whose answers no longer match current behavior.
- Confusing Time Travel (user-accessible, configurable) with Fail-safe (Snowflake-managed recovery, not user-queryable).
- Mixing up scaling up (bigger warehouse) and scaling out (more clusters).
- Overlooking role hierarchy and ownership when answering access questions.

## Learn more

- [Snowflake certifications](https://learn.snowflake.com/en/certifications/)

## Knowledge check

### Many users run small dashboard queries at the same time, and queries are queuing. Which change addresses this most directly?
- [ ] Increase the warehouse from SMALL to XLARGE
- [x] Configure a multi-cluster warehouse so additional clusters start under load
- [ ] Add a clustering key to the main table
- [ ] Disable the result cache
> Queuing from concurrency is solved by scaling out with more clusters; scaling up mainly speeds individual large queries.

### A table was accidentally dropped two hours ago. What is the quickest recovery, assuming default settings?
- [ ] Contact Snowflake Support to restore from Fail-safe
- [x] Run UNDROP TABLE within the Time Travel retention period
- [ ] Recreate the table from the result cache
- [ ] Clone the table from its stream
> Dropped objects can be restored with UNDROP while still within Time Travel retention; Fail-safe is a last resort handled by Snowflake.

### Which layer of Snowflake's architecture handles authentication, metadata, and query optimization?
- [ ] Storage layer
- [ ] Virtual warehouse layer
- [x] Cloud services layer
- [ ] Client layer
> The cloud services layer coordinates authentication, metadata management, query parsing, and optimization.
