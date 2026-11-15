# Gen2 Standard Warehouses

Generation 2 (Gen2) standard warehouses are the next generation of Snowflake's standard virtual warehouse, running on faster hardware with software optimizations for table scans and for DELETE, UPDATE, and MERGE operations. For most analytics and data engineering workloads, queries finish faster and a warehouse can do more work at once, which can lower cost, raise performance, or both.

## How it works

You select the generation on a standard warehouse with either clause:

- `GENERATION = '1'` or `GENERATION = '2'` (recommended)
- `RESOURCE_CONSTRAINT = STANDARD_GEN_1` or `STANDARD_GEN_2`

Key facts from the documentation:

- According to the Gen2 documentation, if you create a standard warehouse without specifying `GENERATION`, Snowflake defaults to Gen2 unless Gen2 is not available in your region.
- Gen2 is available on AWS, Azure, and Google Cloud in most regions; a few regions are excluded (check the region list in the docs).
- Gen2 is **not** available for X5LARGE and X6LARGE.
- Gen2 applies to standard warehouses only, not Snowpark-optimized warehouses.
- The `GENERATION` clause is currently not available in Snowsight; use SQL.
- The generation appears in the `resource_constraint` column of `SHOW WAREHOUSES`.
- Gen2 credit consumption per hour differs from Gen1; see the Snowflake Service Consumption Table. Faster completion is what offsets the rate difference.

Converting a running warehouse: in-flight queries finish on Gen1 resources while new queries run on Gen2, and you are billed for both until the old queries complete. Converting while suspended avoids the overlap; converting while running maximizes availability.

Query Acceleration Service: a **newly created** Gen2 warehouse has QAS enabled by default with `QUERY_ACCELERATION_MAX_SCALE_FACTOR = 8`. Altering an existing Gen1 warehouse to Gen2 leaves QAS in its previous state.

Replication: if you replicate accounts for failover, secondary regions must support Gen2, or Gen2 warehouses may not resume there after failover. Snowflake does not convert them to Gen1 automatically.

## Example

Create a Gen2 warehouse explicitly:

```sql
CREATE OR REPLACE WAREHOUSE transform_wh
  GENERATION = '2'
  WAREHOUSE_SIZE = 'MEDIUM'
  AUTO_SUSPEND = 120
  AUTO_RESUME = TRUE;
```

Convert an existing Gen1 warehouse, suspending first to avoid double billing:

```sql
ALTER WAREHOUSE legacy_etl_wh SUSPEND;
ALTER WAREHOUSE legacy_etl_wh SET GENERATION = '2';
ALTER WAREHOUSE legacy_etl_wh RESUME;
```

Disable QAS on a new Gen2 warehouse if you want to evaluate Gen2 on its own:

```sql
ALTER WAREHOUSE transform_wh SET ENABLE_QUERY_ACCELERATION = FALSE;
```

Check generation and QAS settings:

```sql
SHOW WAREHOUSES LIKE 'TRANSFORM_WH'
  ->> SELECT "name", "size", "resource_constraint", "enable_query_acceleration"
        FROM $1;
```

## Best practices

- Benchmark before and after: run the same workload on Gen1 and Gen2 and compare elapsed time and total credits, not just the hourly rate.
- Prioritize DML-heavy pipelines (MERGE, UPDATE, DELETE) and scan-heavy analytics, which benefit most from Gen2 optimizations.
- After moving to Gen2, re-check sizing; a smaller Gen2 warehouse may meet the same SLA.
- Verify Gen2 support in all replication target regions before relying on failover.
- Be explicit about QAS: new Gen2 warehouses enable it by default, which adds separately billed serverless credits.

## Common pitfalls

- Comparing only credits per hour and concluding Gen2 is more expensive without measuring runtime.
- Trying to create 5X-Large or 6X-Large Gen2 warehouses.
- Converting a busy warehouse and paying for two sets of compute during the transition.
- Assuming that converting Gen1 to Gen2 turns on QAS; it does not.

## Learn more

- [Snowflake generation 2 standard warehouses](https://docs.snowflake.com/en/user-guide/warehouses-gen2)
- [ALTER WAREHOUSE](https://docs.snowflake.com/en/sql-reference/sql/alter-warehouse)

## Knowledge check

### A team converts a busy Gen1 warehouse to Gen2 while long queries are still running. What happens?
- [ ] The running queries are canceled and restarted on Gen2
- [x] Running queries finish on Gen1 while new queries run on Gen2, and both are billed during the overlap
- [ ] The change is rejected until the warehouse is suspended
- [ ] All queries immediately move to Gen2 hardware
> Existing queries complete on the original resources while new ones use Gen2, so you pay for both until the old queries finish.

### Which statement about Gen2 and the Query Acceleration Service is correct?
- [ ] Altering a Gen1 warehouse to Gen2 always enables QAS
- [x] Newly created Gen2 warehouses have QAS enabled by default with a max scale factor of 8
- [ ] QAS cannot be used with Gen2 warehouses
- [ ] Gen2 warehouses use QAS with an unlimited scale factor by default
> New Gen2 warehouses enable QAS with a default scale factor of 8, while converting an existing warehouse keeps its prior QAS setting.

### How should you decide whether Gen2 saves money for a pipeline?
- [ ] Compare the published credits-per-hour only
- [x] Run the workload on both generations and compare total credits and elapsed time
- [ ] Assume savings because Gen2 is newer
- [ ] Check whether the warehouse is X6LARGE
> Gen2 has a different hourly rate, so the true comparison is total credits consumed for the same work, which depends on how much faster it runs.
