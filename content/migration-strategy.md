# Migrating to Snowflake

Migrating to Snowflake from a legacy data warehouse (Teradata, Oracle, SQL Server, Redshift, and others) is a program of assessment, code conversion, data movement, validation, and cutover, not a single copy job. The key architectural choice is how much to re-architect along the way, and the key risk control is proving that the migrated system produces the same results before users and pipelines switch over.

## How it works

**1. Assessment**

Inventory every object (tables, views, procedures, functions, ETL jobs, scheduled scripts, BI reports) and its dependencies and usage. Classify each item: migrate as-is, rewrite, replace with a native feature, or retire. Unused objects are common and are the cheapest thing to migrate. SnowConvert AI generates assessment reports, conversion issue lists, and effort estimates for supported sources, and the Snowflake AIM (AI Migrations) tooling adds agent-guided workflows on top.

**2. Strategy: lift-and-shift vs re-architect**

- **Lift-and-shift** converts schemas and code with minimal changes. It is the fastest path to decommissioning the legacy platform and reduces risk by changing one thing at a time. The cost is that legacy patterns, such as procedural row-by-row logic and over-indexed staging, carry over.
- **Re-architect** redesigns pipelines around Snowflake features, such as dynamic tables instead of scheduled procedures, ELT in SQL or dbt, layered architecture, and native sharing. It delivers more long-term value but increases scope and validation effort.
- Most programs use a hybrid: lift-and-shift the bulk to hit the decommission date, and re-architect a few high-value or high-cost workloads, often in a later wave.

**3. Code conversion**

SnowConvert AI translates DDL, DML, and procedural code (for example T-SQL, PL/SQL, Teradata BTEQ and stored procedures) to Snowflake SQL and Snowflake Scripting. It flags constructs it cannot convert automatically with issue codes (EWIs) for engineers to resolve. It can also convert some ETL, for example SSIS packages into dbt projects. Plan engineering time for the flagged items, which is where the real effort usually sits.

**4. Data migration**

Bulk historical loads typically extract to cloud storage (Parquet or CSV) and load with COPY INTO. For large estates, SnowConvert AI data migration uses an orchestrator and workers, deployable on Snowpark Container Services or your own infrastructure, to parallelize extraction and loading. Incremental change capture or a final delta load covers the gap until cutover.

**5. Validation**

Validate at increasing depth: schema (columns and types), aggregate metrics (row counts, sums, min and max, null counts), and row-level fingerprints for critical tables. SnowConvert AI data validation implements these levels and can run incrementally. Also validate behavior: run representative reports and pipeline outputs on both systems and compare results.

**6. Cutover**

Run both systems in parallel for a defined period, freeze changes on the legacy side, apply the final delta, re-point BI tools and applications, and keep a rollback plan until sign-off.

## Example

A hand-written reconciliation check you can run alongside tool-based validation, comparing aggregates for one table between the legacy extract (loaded to a reconciliation schema) and the migrated target:

```sql
WITH src AS (
  SELECT COUNT(*) AS row_cnt, SUM(net_amount) AS amt, MAX(order_date) AS max_dt
  FROM recon.legacy_snapshot.orders
),
tgt AS (
  SELECT COUNT(*) AS row_cnt, SUM(net_amount) AS amt, MAX(order_date) AS max_dt
  FROM sales_db.curated.orders
)
SELECT src.row_cnt = tgt.row_cnt AS rows_match,
       src.amt     = tgt.amt     AS amount_match,
       src.max_dt  = tgt.max_dt  AS max_date_match
FROM src, tgt;
```

Bulk-load an extracted Parquet partition from cloud storage:

```sql
COPY INTO sales_db.curated.orders
  FROM @migration.stages.legacy_extract/orders/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = ABORT_STATEMENT;
```

## Best practices

- Retire before you migrate: use query and usage history from the source to drop unused objects from scope.
- Migrate in waves organized by dependency (lineage) and business domain, and make each wave end with users working on Snowflake.
- Treat converted code as code: put it in Git, deploy with CI/CD, and add tests during conversion.
- Define validation acceptance criteria per table and report before the migration starts, including accepted differences such as timestamp precision or collation.
- Set up the target platform foundations first: RBAC framework, warehouses and budgets, network and authentication policies, and naming conventions.
- Measure cost and performance on Snowflake during parallel runs, and right-size warehouses before cutover.

## Common pitfalls

- Treating conversion output as finished. Flagged items, dynamic SQL, and semantic differences (NULL handling, collation, implicit casts) need human review.
- Validating only row counts, which misses truncation, rounding, and timezone errors.
- Rebuilding the legacy platform's workarounds, such as indexes, manual statistics, and fine-grained partition management, that Snowflake does not need.
- Underestimating ETL and BI repointing, which often takes more effort than the database objects.
- Cutting over without a rollback plan or a freeze window on the source system.

## Learn more

- [Snowflake AIM data migration and validation](https://docs.snowflake.com/en/migrations/aim-for-datawarehouses/data-migration-validation/overview)
- [SnowConvert AI release notes](https://docs.snowflake.com/en/migrations/snowconvert-docs/general/release-notes/release-notes/README)

## Knowledge check

### A company must exit its Teradata contract in nine months, and it also wants to modernize pipelines. What strategy best balances both goals?
- [ ] Re-architect everything before migrating any data
- [x] Lift-and-shift most workloads with automated conversion to meet the deadline, then re-architect selected high-value pipelines in later waves
- [ ] Migrate only the data and rebuild all code after the contract ends
- [ ] Run both platforms indefinitely
> A hybrid approach reduces deadline risk by changing one thing at a time for the bulk of the estate, while still capturing modernization benefits where they matter most.

### Row counts match for a migrated fact table, but finance reports differ by small amounts. What validation was most likely missing?
- [ ] Schema validation
- [x] Aggregate and row-level comparisons of values, which would reveal rounding, precision, or type conversion differences
- [ ] A check that the warehouse was large enough
- [ ] A comparison of table comments
> Row counts cannot detect value-level differences. Metric comparisons (sums, min and max) and row fingerprints catch rounding, truncation, and casting issues.

### After running SnowConvert AI, several procedures contain EWI markers. What do these represent?
- [ ] Successful conversions that need no action
- [ ] Performance warnings that are safe to ignore
- [x] Constructs that could not be converted automatically or need review, which engineers must resolve before deployment
- [ ] Objects that SnowConvert deleted
> EWIs flag items the converter could not translate with confidence. They are where most of the manual conversion effort sits, so plan for them in estimates.
