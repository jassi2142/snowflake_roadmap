# File Formats

A file format tells Snowflake how to read (or write) the data in staged files: what type the files are, how fields and records are separated, how they are compressed, and how to treat special values such as NULLs. Getting the file format right is the difference between a clean load and a load full of parsing errors.

## How it works

Snowflake supports these format types for loading: **CSV** (which covers any delimited text, such as TSV or pipe-delimited), **JSON**, **AVRO**, **ORC**, **PARQUET**, and **XML**. For unloading with `COPY INTO <location>`, the supported types are CSV, JSON, and Parquet.

You can describe a format in three places, and the most specific one wins:

1. Inline in the `COPY INTO` statement with `FILE_FORMAT = (TYPE = CSV ...)`.
2. As a default on a stage, using `CREATE STAGE ... FILE_FORMAT = ...`.
3. As a reusable **named file format** object created with `CREATE FILE FORMAT`, which you reference with `FILE_FORMAT = (FORMAT_NAME = 'my_format')`.

Named file formats are the usual choice because many stages and loads can share one definition.

Key CSV options and their defaults:

- `FIELD_DELIMITER`: default comma.
- `RECORD_DELIMITER`: default newline.
- `SKIP_HEADER`: default 0 lines skipped.
- `PARSE_HEADER`: default FALSE. When TRUE, the first row supplies column names for schema detection and `MATCH_BY_COLUMN_NAME`. It cannot be combined with `SKIP_HEADER`.
- `FIELD_OPTIONALLY_ENCLOSED_BY`: default NONE. Set it to `'"'` when text fields are quoted.
- `NULL_IF`: default `\N`. Strings listed here become SQL NULL.
- `EMPTY_FIELD_AS_NULL`: default TRUE.
- `ERROR_ON_COLUMN_COUNT_MISMATCH`: default TRUE.
- `COMPRESSION`: default AUTO, which detects gzip, bz2, zstd, and others automatically. Brotli is the exception and must be specified explicitly.

Useful JSON options include `STRIP_OUTER_ARRAY` (remove the outer `[ ]` so each element becomes a row) and `STRIP_NULL_VALUES`. For Parquet, Snowflake recommends `USE_VECTORIZED_SCANNER = TRUE` for new workloads and `BINARY_AS_TEXT = FALSE` to avoid conversion issues.

## Example

Create a reusable format for quoted, pipe-delimited files with a header row, then use it in a load.

```sql
CREATE OR REPLACE FILE FORMAT pipe_csv
  TYPE = CSV
  FIELD_DELIMITER = '|'
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('', 'NULL')
  TRIM_SPACE = TRUE;

COPY INTO customers
  FROM @my_stage/customers/
  FILE_FORMAT = (FORMAT_NAME = 'pipe_csv');
```

Create a JSON format that turns each element of a top-level array into its own row.

```sql
CREATE OR REPLACE FILE FORMAT json_array
  TYPE = JSON
  STRIP_OUTER_ARRAY = TRUE;
```

You can also use a file format to preview staged files before loading them:

```sql
SELECT $1, $2, $3
FROM @my_stage/customers/ (FILE_FORMAT => 'pipe_csv')
LIMIT 10;
```

## Best practices

- Create named file formats and reuse them, rather than repeating inline options in every COPY statement.
- Query staged files directly with the file format to check parsing before running a full load.
- Set `FIELD_OPTIONALLY_ENCLOSED_BY` whenever text values can contain the delimiter.
- Prefer columnar formats such as Parquet when you control the producer; they carry their own schema and types.
- Use `STRIP_NULL_VALUES = TRUE` for JSON when "null" values carry no meaning, to save storage.

## Common pitfalls

- Forgetting `SKIP_HEADER = 1`, so the header row loads as data or causes type errors.
- Setting both `SKIP_HEADER` and `PARSE_HEADER = TRUE`, which is not supported.
- Leaving `ESCAPE_UNENCLOSED_FIELD` at its backslash default when rows end with a backslash, which merges two rows into one.
- Loading Brotli-compressed files with `COMPRESSION = AUTO`; Brotli is not auto-detected.

## Learn more

- [CREATE FILE FORMAT](https://docs.snowflake.com/en/sql-reference/sql/create-file-format)
- [COPY INTO <table>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)

## Knowledge check

### Your CSV files contain company names such as "Acme, Inc." wrapped in double quotes. Rows fail with too many columns. What is the most likely fix?
- [ ] Set SKIP_HEADER = 2
- [x] Set FIELD_OPTIONALLY_ENCLOSED_BY = '"'
- [ ] Change COMPRESSION to NONE
- [ ] Switch the TYPE to JSON
> Without an enclosing character, the comma inside the quoted value is treated as a field delimiter. FIELD_OPTIONALLY_ENCLOSED_BY tells Snowflake to treat the quoted text as one field.

### A JSON file contains a single array of 10,000 objects. You want one table row per object. Which option helps?
- [ ] NULL_IF
- [ ] PARSE_HEADER
- [x] STRIP_OUTER_ARRAY = TRUE
> STRIP_OUTER_ARRAY removes the enclosing brackets so each element of the array becomes a separate row.

### Why are named file formats generally preferred over inline FILE_FORMAT options?
- [ ] Inline options are not supported by COPY INTO
- [x] One named definition can be reused by many stages and loads, keeping parsing rules consistent
- [ ] Named file formats load data faster
> Named formats are reusable objects, so you define parsing rules once and reference them everywhere. Inline options work but must be repeated in every statement.
