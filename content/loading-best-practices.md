# Bulk Loading at Scale

At scale, the cost and reliability of `COPY INTO` are governed less by syntax than by file layout, warehouse sizing, load metadata behavior, and how you detect and recover from bad data. This topic covers the design decisions senior engineers make when loading terabytes per day: how to size files for parallelism, how to reason about deduplication windows, and how to build validation and monitoring into the pipeline.

## How it works

**Parallelism and file sizing.** The number of load operations that run in parallel cannot exceed the number of files. Snowflake recommends files of roughly **100-250 MB compressed** (or larger) and advises against very large files (for example, 100 GB or more). A single load operation that runs beyond the **24-hour** maximum can be aborted with nothing committed. Small files are not free either: per-file overhead dominates when you have millions of tiny objects, so aggregate small files and split huge ones by line. One exception: large uncompressed RFC 4180 CSV files (over 128 MB) can be scanned in parallel when `MULTI_LINE = FALSE`, `COMPRESSION = NONE`, and `ON_ERROR` is `ABORT_STATEMENT` or `CONTINUE`.

Warehouse size determines how many files are processed concurrently. Scaling up helps only when there are enough files to keep the extra compute busy; a single 50 GB file will not load faster on an XL than an S.

**File selection.** An explicit `FILES` list (up to 1,000 names) is generally fastest, a path prefix is next, and `PATTERN` is generally slowest because it must match against many listed objects.

**Load metadata.** Each table stores per-file load metadata (name, size, ETag, rows parsed, last load time, errors) for **64 days**. Within that window, files with unchanged checksums are skipped. When a file's `LAST_MODIFIED` is older than 64 days and the table's initial load and any successful load of that file are also older than 64 days, the load status is *uncertain* and the file is skipped by default. `LOAD_UNCERTAIN_FILES = TRUE` loads such files while still using any metadata that exists; `FORCE = TRUE` ignores metadata and can duplicate data. Concurrent COPY statements also use this status to avoid loading the same file twice; for highly concurrent loads into one table, Snowflake recommends Snowpipe.

**Error handling trade-offs.**

- `ABORT_STATEMENT` (bulk default): all-or-nothing per statement; best when correctness beats freshness.
- `CONTINUE`: loads good rows; reports one error per file in the COPY output. Use `VALIDATE` afterwards for all errors.
- `SKIP_FILE` variants: buffer the entire file, so they are slower than `CONTINUE` or `ABORT_STATEMENT` and can waste credits when large files are skipped for a few bad rows.

**Validation.** `VALIDATION_MODE` (`RETURN_<n>_ROWS`, `RETURN_ERRORS`, `RETURN_ALL_ERRORS`) checks files without loading. It does not support transformations, `MATCH_BY_COLUMN_NAME`, or Iceberg tables. The `VALIDATE` table function returns errors from a previous load by job ID, also excluding transforming loads.

**Monitoring.** `INFORMATION_SCHEMA.LOAD_HISTORY` covers bulk COPY for 14 days, is capped at 10,000 rows, and excludes Snowpipe. The `COPY_HISTORY` table function (14 days) and `ACCOUNT_USAGE.COPY_HISTORY` view cover both COPY and Snowpipe. Statements aborted by `ABORT_STATEMENT` do not appear in COPY_HISTORY; look for them in `QUERY_HISTORY`.

## Example

Validate a batch before loading, load with `CONTINUE`, then pull every error from that job.

```sql
COPY INTO raw.events
  FROM @landing/events/dt=2026-11-10/
  FILE_FORMAT = (FORMAT_NAME = 'events_csv')
  VALIDATION_MODE = RETURN_ERRORS;

COPY INTO raw.events
  FROM @landing/events/dt=2026-11-10/
  FILE_FORMAT = (FORMAT_NAME = 'events_csv')
  ON_ERROR = CONTINUE;

SELECT * FROM TABLE(VALIDATE(raw.events, JOB_ID => '_last'));
```

Monitor the last day of loads for one table, including partial failures.

```sql
SELECT file_name, status, row_count, row_parsed, first_error_message, last_load_time
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
  TABLE_NAME => 'RAW.EVENTS',
  START_TIME => DATEADD('hour', -24, CURRENT_TIMESTAMP())))
WHERE status <> 'Loaded'
ORDER BY last_load_time DESC;
```

## Best practices

- Have producers emit 100-250 MB compressed files; fix file sizing upstream rather than compensating with bigger warehouses.
- Partition stage paths by time and load each partition promptly, keeping files well inside the 64-day metadata window.
- Run backfills of old files with `LOAD_UNCERTAIN_FILES = TRUE`, not `FORCE = TRUE`, unless the target is empty or idempotency is handled downstream.
- Prefer `CONTINUE` plus `VALIDATE`-driven quarantine for high-volume feeds; reserve `ABORT_STATEMENT` for contract-critical data.
- Use a dedicated loading warehouse so loads do not compete with queries, and size it to the number of files per batch.
- Alert on `COPY_HISTORY` rows with non-loaded status and on failed queries in `QUERY_HISTORY`.

## Common pitfalls

- Loading a single giant file and expecting a larger warehouse to speed it up.
- Using `SKIP_FILE` on very large files and paying to buffer and discard them.
- Relying on `LOAD_HISTORY` for Snowpipe or for more than 10,000 rows.
- Forgetting that truncating a table resets what `LOAD_HISTORY` shows, which can mislead dedup audits.
- Expecting `VALIDATION_MODE` to work on transforming COPY statements.

## Learn more

- [Preparing your data files](https://docs.snowflake.com/en/user-guide/data-load-considerations-prepare)
- [Loading data: considerations](https://docs.snowflake.com/en/user-guide/data-load-considerations-load)
- [COPY INTO <table>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)

## Knowledge check

### A source system exports one 80 GB gzip file per day. Loads are slow, and moving from a Medium to a 2X-Large warehouse barely helps. What is the best fix?
- [ ] Switch ON_ERROR to SKIP_FILE
- [x] Have the producer split output into many files of roughly 100-250 MB compressed
- [ ] Use PATTERN instead of a path
- [ ] Enable FORCE = TRUE
> Parallelism cannot exceed the number of files, so one large file uses little of a larger warehouse. Splitting into many right-sized files lets the compute work in parallel.

### You must backfill files that were staged 6 months ago into a table that was first loaded 5 months ago. Some of those files may already be loaded. Which option best balances completeness and duplicate risk?
- [ ] FORCE = TRUE
- [x] LOAD_UNCERTAIN_FILES = TRUE
- [ ] PURGE = TRUE
- [ ] No option is needed; COPY loads them by default
> These files have uncertain load status and are skipped by default. LOAD_UNCERTAIN_FILES loads them while still using any available load metadata, whereas FORCE ignores metadata and can duplicate data.

### A COPY with ON_ERROR = ABORT_STATEMENT failed on a bad row, but the failure does not appear in COPY_HISTORY. Where should monitoring look?
- [ ] LOAD_HISTORY
- [ ] PIPE_USAGE_HISTORY
- [x] QUERY_HISTORY
> Aborted statements do not ingest any files, so they are not recorded in COPY_HISTORY. The failed statement and its error are visible in QUERY_HISTORY.
