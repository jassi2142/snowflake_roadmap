# COPY INTO

`COPY INTO <table>` is Snowflake's bulk loading command: it reads files from a stage (or directly from a cloud storage URL) and inserts their rows into an existing table using a running virtual warehouse. It is the foundation of batch data loading and is also the statement that Snowpipe runs under the covers.

## How it works

A basic load names a target table, a source location, and a file format:

```sql
COPY INTO my_table
  FROM @my_stage/path/
  FILE_FORMAT = (FORMAT_NAME = 'my_csv_format');
```

You choose which files to load in three ways: by **path** (everything under a prefix), by an explicit **FILES** list (up to 1,000 names, generally the fastest option), or with a **PATTERN** regular expression (generally the slowest).

Snowflake keeps **load metadata** for each table: the name, size, ETag, and row counts of every file it loaded. This metadata expires after **64 days**. While it exists, `COPY` silently skips files it has already loaded, which protects you from loading the same file twice. That is why rerunning a `COPY` often returns "Copy executed with 0 files processed".

Important copy options and their defaults:

- `ON_ERROR`: what to do when a row fails. Default is `ABORT_STATEMENT` for bulk `COPY` (Snowpipe defaults to `SKIP_FILE`). Other values are `CONTINUE`, `SKIP_FILE`, `SKIP_FILE_<n>`, and `'SKIP_FILE_<n>%'`.
- `FORCE`: default FALSE. TRUE reloads files even if they were already loaded, which can duplicate data.
- `PURGE`: default FALSE. TRUE removes files from the stage after a successful load.
- `MATCH_BY_COLUMN_NAME`: default NONE. Set to `CASE_INSENSITIVE` or `CASE_SENSITIVE` to map file columns to table columns by name rather than position (supported for JSON, Avro, ORC, Parquet, and CSV).
- `VALIDATION_MODE`: checks files for errors without loading them.

You can also **transform** data during a load by selecting from the stage with positional references such as `$1`, `$2`, or `$1:field` for semi-structured data. Transformations support column reordering, omission, casts, and a subset of SQL functions, but they cannot be combined with `MATCH_BY_COLUMN_NAME` or `VALIDATION_MODE`.

The output of `COPY` lists each file with its status (`LOADED`, `LOAD_FAILED`, or `PARTIALLY_LOADED`), rows parsed and loaded, and the first error.

## Example

Load CSV files and continue past bad rows, so you can review errors afterwards.

```sql
COPY INTO sales
  FROM @raw_stage/sales/2026/11/
  FILE_FORMAT = (FORMAT_NAME = 'csv_with_header')
  ON_ERROR = CONTINUE;
```

Load Parquet files by matching column names, so column order in the file does not matter.

```sql
COPY INTO customers
  FROM @raw_stage/customers/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
```

Transform during load: pick and cast specific columns and record the source file name.

```sql
COPY INTO orders (order_id, amount, source_file)
  FROM (
    SELECT $1::NUMBER, $3::NUMBER(10,2), METADATA$FILENAME
    FROM @raw_stage/orders/
  )
  FILE_FORMAT = (FORMAT_NAME = 'csv_with_header');
```

## Best practices

- Test a new load with `VALIDATION_MODE = RETURN_ERRORS` before running it for real.
- Organize staged files by date-based paths and load each path shortly after it lands, so load metadata reliably prevents duplicates.
- Use named file formats so every load parses files the same way.
- Capture `METADATA$FILENAME` during loads to make debugging and auditing easier.
- Use a dedicated, appropriately sized warehouse for heavy loading.

## Common pitfalls

- Using `FORCE = TRUE` to "fix" a load that returned 0 files, and duplicating data that had already loaded.
- Expecting `COPY` to load files older than 64 days whose load status is unknown; they are skipped unless you use `LOAD_UNCERTAIN_FILES = TRUE`.
- Leaving `ON_ERROR` at its default and having one bad row abort a large load.
- Combining `MATCH_BY_COLUMN_NAME` with a `SELECT` transformation, which raises a compilation error.

## Learn more

- [COPY INTO <table>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)
- [Loading data: considerations](https://docs.snowflake.com/en/user-guide/data-load-considerations-load)

## Knowledge check

### You rerun the same COPY INTO statement an hour later and get "Copy executed with 0 files processed". What most likely happened?
- [ ] The warehouse was suspended
- [x] The files were already loaded, and load metadata caused COPY to skip them
- [ ] The stage was dropped
- [ ] COPY only runs once per day per table
> Snowflake tracks which files have been loaded into each table for 64 days and skips them to prevent duplicates. This is expected behavior, not an error.

### A nightly load of 200 files fails entirely because one row has a bad date. You prefer to load the good rows and review errors later. Which setting helps?
- [ ] FORCE = TRUE
- [ ] PURGE = TRUE
- [x] ON_ERROR = CONTINUE
> The default ON_ERROR for bulk COPY is ABORT_STATEMENT. CONTINUE loads the valid rows and reports errors so you can investigate them afterwards.

### Which approach to selecting files is generally the fastest?
- [ ] A broad PATTERN regular expression
- [x] An explicit FILES list
- [ ] Loading the entire stage with no path
> An explicit list of file names avoids listing and matching many files. It supports up to 1,000 names per statement.
