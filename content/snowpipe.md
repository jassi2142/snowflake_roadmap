# Snowpipe

Snowpipe is Snowflake's serverless service for continuously loading files as soon as they arrive in a stage. Instead of scheduling `COPY INTO` on a warehouse, you define a pipe once, and Snowflake loads new files in micro-batches, typically within a minute of being notified about them.

## How it works

A **pipe** is a named object that wraps a `COPY INTO <table>` statement. Snowpipe learns about new files in one of two ways:

- **Auto-ingest** (`AUTO_INGEST = TRUE`): your cloud storage publishes an event when a file lands, and Snowflake reads it from a queue. On Amazon S3, Snowflake provides an SQS queue (shown in the `notification_channel` column of `DESC PIPE`), optionally fronted by SNS. On Google Cloud Storage you create a Pub/Sub subscription, and on Azure an Event Grid subscription with a storage queue; both are connected through a **notification integration**.
- **REST API**: your application calls the Snowpipe `insertFiles` endpoint with a list of file paths. Use this when your application should decide when files load, or where event notifications are not available (for example, S3-compatible storage).

Snowpipe keeps its own **load metadata per pipe** to avoid loading the same file twice. Note that pipe metadata is separate from bulk COPY metadata, so loading the same files with both Snowpipe and a manual `COPY` can duplicate data.

Other key behaviors:

- The default `ON_ERROR` for Snowpipe is `SKIP_FILE` (bulk COPY defaults to `ABORT_STATEMENT`).
- A new pipe loads only files that arrive after notifications are configured. `ALTER PIPE ... REFRESH` queues files staged within the last 7 days.
- While a pipe is paused, Snowflake holds its notifications for 14 days. A pipe paused longer than that becomes **stale**.
- `SYSTEM$PIPE_STATUS` reports the execution state and notification details; `COPY_HISTORY` shows per-file results.

**Billing.** Snowpipe charges a fixed number of credits per GB loaded, with no warehouse and no per-file charge. Text formats (CSV, JSON, XML) are billed on their **uncompressed** size, and binary formats (Avro, ORC, Parquet) on their size in storage. Snowflake moved accounts to this per-GB model during 2025. Resource monitors do not control Snowpipe; use budgets instead. Monitor usage with the `PIPE_USAGE_HISTORY` view.

## Example

Create an auto-ingest pipe on S3, then load files staged in the last 7 days.

```sql
CREATE OR REPLACE PIPE raw.orders_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO raw.orders
  FROM @raw.orders_s3_stage
  FILE_FORMAT = (TYPE = JSON)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

-- notification_channel holds the SQS ARN to configure in the S3 event notification
DESC PIPE raw.orders_pipe;

ALTER PIPE raw.orders_pipe REFRESH;
```

Check pipe health and recent load results.

```sql
SELECT SYSTEM$PIPE_STATUS('raw.orders_pipe');

SELECT file_name, status, row_count, first_error_message
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
  TABLE_NAME => 'RAW.ORDERS',
  START_TIME => DATEADD('hour', -1, CURRENT_TIMESTAMP())));
```

Pause and resume a pipe.

```sql
ALTER PIPE raw.orders_pipe SET PIPE_EXECUTION_PAUSED = TRUE;
ALTER PIPE raw.orders_pipe SET PIPE_EXECUTION_PAUSED = FALSE;
```

## Best practices

- Give each pipe its own non-overlapping location and end stage URLs and paths with `/`; overlapping pipes load the same files twice.
- Filter events at the source (prefix or suffix filters) instead of relying on `PATTERN`, which still processes every notification.
- If files accumulate slowly, write a new file about once per minute; files of 100-250 MB compressed load most efficiently.
- Prefer Parquet or Avro when you control the producer, since compressed CSV is billed on its uncompressed size.
- Set up alerts or error notifications for failed loads rather than polling.

## Common pitfalls

- Backfilling with a manual `COPY` into the same table and creating duplicates, because pipe and table load metadata are separate.
- Expecting a new pipe to pick up old files automatically.
- Leaving a pipe paused for more than 14 days and ending up with a stale pipe.
- Trying to cap Snowpipe spend with a resource monitor.

## Learn more

- [Snowpipe](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro)
- [Automate Snowpipe with cloud event notifications](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-auto)
- [Snowpipe costs](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-billing)

## Knowledge check

### Two pipes watch s3://bucket/orders and s3://bucket/orders/2026/ and both load into the same table. What happens?
- [ ] Snowflake detects the overlap and loads each file once
- [x] Files in the overlapping path are loaded by both pipes, producing duplicate rows
- [ ] The second pipe fails to create
> Each pipe loads every file in its location independently. Overlapping locations cause the same file to be loaded twice into the target table.

### Your team loads 1 TB per day of gzip CSV that is 5 TB uncompressed. How is the data billed under current Snowpipe pricing?
- [ ] On compressed size, 1 TB
- [x] On uncompressed size, 5 TB
- [ ] Per file, regardless of size
- [ ] On warehouse seconds used
> Text formats such as CSV are billed on uncompressed size. Converting the feed to Parquet would bill on the size in storage instead.

### You created a new auto-ingest pipe, but files that landed yesterday were not loaded. What should you do?
- [ ] Recreate the stage
- [x] Run ALTER PIPE ... REFRESH to queue files staged in the last 7 days
- [ ] Set FORCE = TRUE on the pipe
> A pipe only receives notifications for files that arrive after it is configured. REFRESH queues recently staged files, up to 7 days old.
