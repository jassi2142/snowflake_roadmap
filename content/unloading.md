# Unloading Data

Unloading is the reverse of loading: you export table data or query results into files in a stage, using `COPY INTO <location>`. Teams unload data to hand files to external systems, feed data lakes, archive results, or share extracts with partners who do not use Snowflake.

## How it works

The command writes the result of a table or a `SELECT` query into one or more files:

```sql
COPY INTO @my_stage/exports/orders_
  FROM (SELECT * FROM orders WHERE order_date = CURRENT_DATE - 1)
  FILE_FORMAT = (TYPE = PARQUET);
```

The destination can be an internal stage (user, table, or named stage), a named external stage, or an external cloud storage URL. From an internal stage, you download files to your computer with the `GET` command.

Supported unload formats are **CSV**, **JSON**, and **PARQUET**. JSON can only be unloaded from VARIANT data, so you typically build it with `OBJECT_CONSTRUCT`. By default, CSV and JSON files are compressed with gzip, and Parquet files with Snappy.

Key copy options:

- `SINGLE`: default FALSE. Snowflake writes multiple files in parallel by default. Set TRUE to produce one file.
- `MAX_FILE_SIZE`: an upper size target for each file. The default is 16 MB. Snowflake still splits output across parallel threads, so this does not directly control how many files you get.
- `HEADER`: default FALSE. TRUE writes column names into CSV files (into every file, when there are several).
- `OVERWRITE`: default FALSE. Replaces existing files with matching names.
- `INCLUDE_QUERY_ID`: adds the query ID to file names so repeated unloads do not collide.
- `PARTITION BY <expr>`: splits output into folders based on an expression, such as a date. It cannot be combined with `SINGLE = TRUE` or `OVERWRITE = TRUE`.
- `VALIDATION_MODE = RETURN_ROWS`: returns the query results instead of writing files, so you can check them first.

## Example

Unload yesterday's orders to a single gzip-compressed CSV file with a header row.

```sql
COPY INTO @export_stage/daily/orders.csv.gz
  FROM (SELECT order_id, customer_id, amount FROM orders
        WHERE order_date = CURRENT_DATE - 1)
  FILE_FORMAT = (TYPE = CSV COMPRESSION = GZIP)
  HEADER = TRUE
  SINGLE = TRUE
  MAX_FILE_SIZE = 1000000000;
```

Unload to Parquet, partitioned by date into separate folders.

```sql
COPY INTO @lake_stage/orders/
  FROM (SELECT *, TO_VARCHAR(order_date, 'YYYY-MM-DD') AS dt FROM orders)
  PARTITION BY ('dt=' || dt)
  FILE_FORMAT = (TYPE = PARQUET)
  HEADER = TRUE;
```

Download an unloaded file from an internal stage (run from SnowSQL or Snowflake CLI).

```sql
GET @export_stage/daily/orders.csv.gz file:///tmp/exports/;
```

## Best practices

- Let Snowflake write multiple files when the consumer can read a folder; parallel unloads are faster than `SINGLE = TRUE`.
- Use a new path per run, or `INCLUDE_QUERY_ID = TRUE`, to avoid mixing files from different unloads.
- Prefer Parquet for downstream analytics engines; it keeps column names and types.
- Partition only on dates, timestamps, or booleans. Partition values appear in file names, so avoid sensitive columns.
- Preview output with `VALIDATION_MODE = RETURN_ROWS` before writing large exports.

## Common pitfalls

- Expecting a large `MAX_FILE_SIZE` to produce one file; you need `SINGLE = TRUE` for that.
- Relying on `OVERWRITE = TRUE` to prevent duplicates; file names can differ between runs, so old files may remain.
- Forgetting `HEADER = TRUE` for CSV consumers that expect column names.
- Trying to unload a relational table directly to JSON without converting rows to VARIANT.

## Learn more

- [COPY INTO <location>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-location)

## Knowledge check

### You set MAX_FILE_SIZE to 5 GB for a 200 MB table, but COPY INTO still writes several small files. Why?
- [ ] MAX_FILE_SIZE is ignored for CSV
- [x] Snowflake unloads in parallel by default; you need SINGLE = TRUE to produce one file
- [ ] The warehouse is too small
- [ ] Compression always splits files
> MAX_FILE_SIZE is only an upper bound. Output is split across parallel threads unless SINGLE = TRUE is set.

### A partner needs a daily CSV extract with column names. Which option ensures the names are included?
- [ ] OVERWRITE = TRUE
- [ ] PARTITION BY
- [x] HEADER = TRUE
> HEADER defaults to FALSE for unloads. Setting it to TRUE writes column headings into each output file.

### Which unload formats does COPY INTO <location> support?
- [ ] CSV, JSON, Avro, ORC, Parquet, and XML
- [x] CSV, JSON, and Parquet
- [ ] CSV only
> Unloading supports CSV, JSON, and Parquet. Avro, ORC, and XML are supported only for loading.
