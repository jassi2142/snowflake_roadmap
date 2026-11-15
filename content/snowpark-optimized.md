# Snowpark-optimized Warehouses

Snowpark-optimized warehouses are a warehouse type that provides much more memory per node than standard warehouses and lets you choose the CPU architecture. They exist for Snowpark workloads, such as machine learning training in stored procedures, that would run out of memory or need x86-specific libraries on a standard warehouse.

## How it works

You create one by setting `WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED'`. By default it provides **16x the memory per node** of a standard warehouse. The `RESOURCE_CONSTRAINT` property lets you pick memory and CPU architecture:

| Memory (up to) | RESOURCE_CONSTRAINT values | Minimum warehouse size |
| --- | --- | --- |
| 16 GB | MEMORY_1X, MEMORY_1X_x86 | XSMALL |
| 256 GB | MEMORY_16X, MEMORY_16X_x86 | MEDIUM |
| 1 TB | MEMORY_64X, MEMORY_64X_x86 | LARGE |

- The default resource constraint is `MEMORY_16X`.
- The `_x86` variants pin the warehouse to x86 CPUs, useful for packages that depend on that architecture.
- The 1 TB options are in preview and currently available only on AWS. All other options are generally available on all cloud platforms.
- Initial creation and resumption may take longer than for standard warehouses.
- You can change the warehouse type or resource constraint while the warehouse is running or suspended. If you change it while running, in-flight queries finish on the old resources while new queries use the new ones, and you pay for both during the overlap.
- Snowpark-optimized warehouses are not available as Gen2; the `GENERATION` clause applies only to standard warehouses.
- Credit rates differ from standard warehouses; see the Snowflake Service Consumption Table for current numbers.

Typical candidates are single-node ML training in a Python stored procedure, memory-heavy UDFs or UDTFs, and code that loads large models or datasets into memory. Workloads that do not use Snowpark usually gain nothing from this type.

## Example

Create a Medium Snowpark-optimized warehouse with the default 16x memory:

```sql
CREATE OR REPLACE WAREHOUSE snowpark_opt_wh WITH
  WAREHOUSE_SIZE = 'MEDIUM'
  WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED';
```

Create a Large warehouse with 256 GB memory on x86 CPUs:

```sql
CREATE WAREHOUSE ml_training_wh WITH
  WAREHOUSE_SIZE = 'LARGE'
  WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED'
  RESOURCE_CONSTRAINT = 'MEMORY_16X_X86';
```

Reduce memory for a lighter workload, suspending first to avoid paying for both configurations:

```sql
ALTER WAREHOUSE ml_training_wh SUSPEND;
ALTER WAREHOUSE ml_training_wh SET RESOURCE_CONSTRAINT = 'MEMORY_1X_x86';
```

Run a training procedure on it:

```sql
USE WAREHOUSE ml_training_wh;
CALL train_churn_model('ANALYTICS.ML.CUSTOMER_FEATURES');
```

## Best practices

- Use a separate Snowpark-optimized warehouse for ML and memory-heavy code; keep SQL analytics on standard warehouses.
- Choose the smallest memory option that avoids out-of-memory errors; test with realistic data volumes.
- Use x86 constraints only when a dependency requires it.
- Remember that single-node training does not benefit from multiple clusters; a bigger memory option is usually the lever.
- Account for slower startup when scheduling jobs with tight windows.

## Common pitfalls

- Moving ordinary SQL workloads to Snowpark-optimized warehouses expecting a speedup.
- Choosing a resource constraint below its minimum warehouse size (for example, MEMORY_16X on Small).
- Changing the type while the warehouse is busy and being surprised by overlapping charges.
- Assuming the 1 TB option is available on Azure or Google Cloud.

## Learn more

- [Snowpark-optimized warehouses](https://docs.snowflake.com/en/user-guide/warehouses-snowpark-optimized)

## Knowledge check

### A Python stored procedure training an XGBoost model fails with out-of-memory errors on a standard Large warehouse. What is the best next step?
- [ ] Add more clusters to the standard warehouse
- [x] Run it on a Snowpark-optimized warehouse with sufficient memory
- [ ] Enable the Query Acceleration Service
- [ ] Increase STATEMENT_TIMEOUT_IN_SECONDS
> Snowpark-optimized warehouses provide much more memory per node, which is what single-node training in a stored procedure needs.

### Which RESOURCE_CONSTRAINT gives up to 256 GB of memory on x86 CPUs?
- [ ] MEMORY_1X_x86
- [x] MEMORY_16X_x86
- [ ] MEMORY_64X
- [ ] STANDARD_GEN_2
> MEMORY_16X_x86 provides up to 256 GB of memory and pins the CPU architecture to x86.

### What is the minimum warehouse size for a MEMORY_16X Snowpark-optimized warehouse?
- [ ] X-Small
- [ ] Small
- [x] Medium
- [ ] Large
> The 256 GB (MEMORY_16X) options require at least a Medium warehouse.
