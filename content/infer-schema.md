# Schema Detection & Evolution (INFER_SCHEMA, USING TEMPLATE, ENABLE_SCHEMA_EVOLUTION)

Snowflake can read the column definitions from staged files and create a matching table for you, then keep that table's schema in step as new files add columns. Together, `INFER_SCHEMA`, `CREATE TABLE ... USING TEMPLATE`, and `ENABLE_SCHEMA_EVOLUTION` remove much of the manual DDL work in file-based pipelines, especially for semi-structured and columnar sources.

## How it works

**INFER_SCHEMA** is a table function that scans staged files and returns one row per detected column, with `COLUMN_NAME`, `TYPE`, `NULLABLE`, `EXPRESSION`, `FILENAMES`, and `ORDER_ID`. It supports Parquet, Avro, ORC, JSON, and CSV. Notes that matter in practice:

- It works with named stages (internal or external) and user stages, but **not table stages**.
- For CSV, set `PARSE_HEADER = TRUE` in the file format to take column names from the header row; otherwise columns are named `c1`, `c2`, and so on.
- For CSV and JSON, every column is reported as nullable, and all timestamp variants are returned as `TIMESTAMP_NTZ`.
- `MAX_FILE_COUNT` and `MAX_RECORDS_PER_FILE` (CSV and JSON only) limit how much data is scanned, at some cost to accuracy.
- `IGNORE_CASE => TRUE` returns uppercase column names.
- `KIND => 'ICEBERG'` returns Iceberg types; use it when the target is an Iceberg table.

**USING TEMPLATE** turns that output into DDL. `CREATE TABLE`, `CREATE EXTERNAL TABLE`, and `CREATE ICEBERG TABLE` accept a subquery that aggregates the `INFER_SCHEMA` rows into an array of objects. If the subquery returns an empty array, the statement fails with "template must be a non-null JSON array".

**ENABLE_SCHEMA_EVOLUTION** is a table property. Schema evolution happens when all of these are true:

- The table has `ENABLE_SCHEMA_EVOLUTION = TRUE`.
- The load uses `COPY INTO <table>` (or Snowpipe) with `MATCH_BY_COLUMN_NAME`.
- The loading role has the `EVOLVE SCHEMA` or `OWNERSHIP` privilege on the table.

For CSV with `PARSE_HEADER`, `ERROR_ON_COLUMN_COUNT_MISMATCH` must also be FALSE. Evolution can **add new columns** and **drop NOT NULL constraints** for columns missing from new files. By default, one COPY operation can add at most 100 columns and evolve at most one schema; there is no limit on dropping NOT NULL. Changes are recorded in a `SchemaEvolutionRecord` visible in `DESCRIBE TABLE`, `SHOW COLUMNS`, and the `COLUMNS` views. Evolution does not apply to `INSERT` statements and is not supported by tasks.

## Example

Create a table whose columns come from staged Parquet files.

```sql
CREATE OR REPLACE FILE FORMAT parquet_fmt TYPE = PARQUET;

SELECT *
FROM TABLE(INFER_SCHEMA(
  LOCATION    => '@raw_stage/events/',
  FILE_FORMAT => 'parquet_fmt'));

CREATE OR REPLACE TABLE events
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*)) WITHIN GROUP (ORDER BY order_id)
    FROM TABLE(INFER_SCHEMA(
      LOCATION    => '@raw_stage/events/',
      FILE_FORMAT => 'parquet_fmt')))
  ENABLE_SCHEMA_EVOLUTION = TRUE;
```

Allow a loader role to evolve the schema, then load by column name. A new column in the files is added automatically.

```sql
GRANT EVOLVE SCHEMA ON TABLE events TO ROLE loader;

COPY INTO events
  FROM @raw_stage/events/
  FILE_FORMAT = (FORMAT_NAME = 'parquet_fmt')
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

DESCRIBE TABLE events;
```

## Best practices

- Review `INFER_SCHEMA` output before creating production tables; inferred types (for example, wide VARCHARs or TIMESTAMP_NTZ) may need adjusting.
- Prefer self-describing formats such as Parquet and Avro, which give more accurate types and nullability than CSV or JSON.
- For large result sets, aggregate only `COLUMN_NAME`, `TYPE`, and `NULLABLE` instead of `OBJECT_CONSTRUCT(*)`; the docs warn that results over 128 MB can fail.
- Grant `EVOLVE SCHEMA` deliberately; it lets a pipeline change table structure without a DDL review.
- Monitor `SchemaEvolutionRecord` so downstream consumers learn about new columns.

## Common pitfalls

- Pointing `INFER_SCHEMA` at a table stage, which is not supported.
- Enabling schema evolution but loading without `MATCH_BY_COLUMN_NAME`, so nothing evolves.
- Expecting evolution to change data types or drop columns; it only adds columns and relaxes NOT NULL.
- Manually renaming or modifying an evolved column, which clears its evolution record.

## Learn more

- [INFER_SCHEMA](https://docs.snowflake.com/en/sql-reference/functions/infer_schema)
- [Enable automatic table schema evolution](https://docs.snowflake.com/en/user-guide/data-load-schema-evolution)

## Knowledge check

### A table has ENABLE_SCHEMA_EVOLUTION = TRUE, but a COPY of files containing a new column loads without adding it. The loading role owns the table. What is most likely missing?
- [ ] The table must be transient
- [x] The COPY statement does not use MATCH_BY_COLUMN_NAME
- [ ] Schema evolution only works with INSERT
- [ ] The warehouse must be at least size Large
> Evolution requires the table property, a privileged role, and a COPY or Snowpipe load that uses MATCH_BY_COLUMN_NAME. Without column-name matching, Snowflake has no way to map new file columns.

### Which change can automatic schema evolution make?
- [ ] Change a column from NUMBER to VARCHAR
- [ ] Drop a column that no longer appears in files
- [x] Add a new column and drop a NOT NULL constraint
> Schema evolution adds new columns and relaxes NOT NULL constraints for columns missing from new data. It does not change types or drop columns.

### You run INFER_SCHEMA against CSV files and get columns named C1, C2, C3. What should you change?
- [ ] Set IGNORE_CASE => TRUE
- [x] Use a file format with PARSE_HEADER = TRUE
- [ ] Set SKIP_HEADER = 1 together with PARSE_HEADER = TRUE
> PARSE_HEADER = TRUE takes column names from the first row. It cannot be combined with SKIP_HEADER.
