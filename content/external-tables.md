# External Tables

An external table lets you query files in an external stage (Amazon S3, Google Cloud Storage, or Azure) with SQL, as if they were a table, without loading the data into Snowflake. It suits data lake files that other systems own, occasional exploration of raw data, and cases where copying data is undesirable, though for Parquet-heavy lakehouse workloads Snowflake now generally points to Iceberg tables instead.

## How it works

Snowflake stores only **file-level metadata** for an external table (file names, version identifiers, and related properties); the data itself stays in your cloud storage. External tables can read any format that `COPY INTO <table>` supports **except XML**, and they are **read-only**: no INSERT, UPDATE, or DELETE.

Every external table includes:

- `VALUE`: a VARIANT column representing one row of the file.
- `METADATA$FILENAME`: the staged file name and path.
- `METADATA$FILE_ROW_NUMBER`: the row number within the file.

You define **virtual columns** as expressions over `VALUE`, such as `order_id NUMBER AS (VALUE:c1::NUMBER)`, which gives typed columns and type checking at query time.

**Partitioning** is strongly recommended. Partition columns are expressions that parse `METADATA$FILENAME`, so the files must be organized in logical paths (for example, by date). Queries that filter on partition columns scan only matching files. Partitions are added automatically on refresh, or manually with `PARTITION_TYPE = USER_SPECIFIED` and `ALTER EXTERNAL TABLE ... ADD PARTITION` (useful when syncing with a Hive or Glue metastore). The partitioning method cannot be changed after creation.

**Metadata refresh.** The metadata must match the files in storage. Refresh it manually with `ALTER EXTERNAL TABLE ... REFRESH`, or automatically with `AUTO_REFRESH = TRUE` driven by cloud event notifications. Automatic refresh overhead is billed under Snowpipe and grows with the number of files added. External tables do not support storage versioning (for example, S3 object versioning).

**Performance.** Queries are usually slower than native tables. Snowflake recommends Parquet files of 256-512 MB (row groups of 16-256 MB) and 16-256 MB for other formats. **Materialized views** over external tables (Enterprise Edition) can significantly speed up frequent or complex queries.

## Example

Create a partitioned external table over Parquet files organized as `orders/2026/11/10/...`, where `lake_stage` points at the bucket root so `METADATA$FILENAME` begins with `orders/`.

```sql
CREATE OR REPLACE EXTERNAL TABLE ext_orders (
  order_date DATE AS TO_DATE(
    SPLIT_PART(METADATA$FILENAME, '/', 2) || '-' ||
    SPLIT_PART(METADATA$FILENAME, '/', 3) || '-' ||
    SPLIT_PART(METADATA$FILENAME, '/', 4)),
  order_id   NUMBER        AS (VALUE:order_id::NUMBER),
  amount     NUMBER(10,2)  AS (VALUE:amount::NUMBER(10,2))
)
  PARTITION BY (order_date)
  LOCATION = @lake_stage/orders/
  FILE_FORMAT = (TYPE = PARQUET)
  AUTO_REFRESH = TRUE;
```

Query it with a partition filter so only matching files are scanned, and refresh manually when needed.

```sql
SELECT order_id, amount
FROM ext_orders
WHERE order_date = '2026-11-10';

ALTER EXTERNAL TABLE ext_orders REFRESH;
```

## Best practices

- Always partition on fields encoded in the file path, and filter on partition columns in queries.
- Define typed virtual columns and query them directly; queries on typed columns are better optimized than raw `VALUE` paths.
- Use materialized views for frequently queried subsets (Enterprise Edition).
- Use `REPLACE_INVALID_CHARACTERS = TRUE` in the file format so rows with invalid UTF-8 are not silently omitted.
- For Parquet data lakes, evaluate Iceberg tables, which Snowflake recommends for better query performance.

## Common pitfalls

- Forgetting to refresh metadata, so new files are invisible and query results are stale.
- Expecting DML to work; external tables are read-only.
- Pointing an external table at XML files, which are not supported.
- Assuming query errors stop the query; files that fail to scan are skipped, so results can be partial.
- Setting up `AUTO_REFRESH` for a Delta Lake external table, which supports only manual refresh.

## Learn more

- [Introduction to external tables](https://docs.snowflake.com/en/user-guide/tables-external-intro)
- [ALTER EXTERNAL TABLE](https://docs.snowflake.com/en/sql-reference/sql/alter-external-table)

## Knowledge check

### New files land in the bucket every hour, but queries on the external table do not show them. AUTO_REFRESH is FALSE. What is the fix?
- [ ] Run COPY INTO on the external table
- [x] Refresh the metadata with ALTER EXTERNAL TABLE ... REFRESH, or configure auto-refresh with event notifications
- [ ] Resize the warehouse
- [ ] Recreate the stage
> Snowflake only knows about files registered in the external table's metadata. Manual or automatic refresh registers new files.

### Queries on a large external table scan every file even though analysts filter by date. What design change helps most?
- [ ] Convert the files to XML
- [x] Define a partition column derived from the date in the file path and filter on it
- [ ] Add more virtual columns
> Partition columns parsed from METADATA$FILENAME let Snowflake skip files that do not match the filter, reducing the data scanned.

### Which operation is supported on an external table?
- [ ] UPDATE
- [ ] INSERT
- [x] SELECT, including joins and views on top
> External tables are read-only. You can query, join, and build views or materialized views on them, but not run DML.
