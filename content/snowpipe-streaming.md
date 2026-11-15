# Snowpipe Streaming

Snowpipe Streaming ingests rows directly into Snowflake tables over an API, with no intermediate files in a stage. It is designed for event streams, IoT telemetry, CDC, and logs where seconds of latency matter, and its high-performance architecture changes both the programming model and the cost model compared with file-based Snowpipe.

## How it works

There are two architectures:

- **Classic**: the original Java Ingest SDK, where clients open channels directly against tables. Billing is based on serverless compute and active client connections.
- **High-performance**: generally available on AWS since September 2025 (check the docs for current regional availability). It uses new SDKs (Java, Python, and Node.js, built on a shared Rust core) plus a REST API for lightweight producers. Snowflake states throughput of up to 10 GB per second per table, with ingest-to-query latency typically under 10 seconds.

The central design change in the high-performance architecture is the **PIPE object**. All streaming data enters a table through a pipe whose `COPY INTO ... FROM TABLE(DATA_SOURCE(TYPE => 'STREAMING'))` definition holds the server-side configuration: column mapping, in-flight transformations, schema validation, and options such as `CLUSTER_AT_INGEST_TIME`. A Snowflake-managed **default pipe** exists for simple table ingestion; you create your own pipe when you need transformations.

**Channels** are the unit of ordering and exactly-once tracking. A client opens a named channel on a pipe and appends rows with an **offset token** (for example, a Kafka partition offset). Snowflake persists the last committed offset token per channel; after a restart, the client reads it with `getLatestCommittedOffsetToken` and replays from there. Channels in the high-performance architecture are scoped to the pipe, not to the table.

**Error handling** is partly asynchronous. Synchronous problems (serialization, throttling with HTTP 429, channel invalidation with HTTP 409) surface on the append call, while schema mismatches validated server-side are reported through `getChannelStatus` (`row_error_count`, last committed offset). REST requests are capped at 4 MB of payload after compression; ZSTD is recommended.

**Cost.** The high-performance architecture is billed per uncompressed GB of data received, and only data values count, not JSON keys. Mapping fields to typed columns with `MATCH_BY_COLUMN_NAME = CASE_SENSITIVE`, instead of landing everything in one VARIANT, reduces both cost and server processing. Usage appears in `ACCOUNT_USAGE.METERING_HISTORY` with service type `SNOWPIPE_STREAMING`.

Schema evolution is supported for standard tables and Snowflake-managed Iceberg tables (for Iceberg, limited to adding new top-level columns).

## Example

A user-defined pipe that maps JSON fields to typed columns and pre-clusters on ingest.

```sql
CREATE OR REPLACE TABLE telemetry (
  device_id     NUMBER,
  reading_ts    TIMESTAMP_NTZ,
  temperature   FLOAT,
  channel_id    NUMBER,
  stream_offset NUMBER
) CLUSTER BY (device_id);

CREATE OR REPLACE PIPE telemetry_pipe AS
  COPY INTO telemetry
  FROM TABLE(DATA_SOURCE(TYPE => 'STREAMING'))
  MATCH_BY_COLUMN_NAME = CASE_SENSITIVE
  CLUSTER_AT_INGEST_TIME = TRUE;
```

Detect gaps per channel using client-supplied metadata columns, following Snowflake's recommended recovery pattern.

```sql
SELECT channel_id, stream_offset,
       LAG(stream_offset) OVER (PARTITION BY channel_id ORDER BY stream_offset) AS prev_offset
FROM telemetry
QUALIFY stream_offset != prev_offset + 1;
```

## Best practices

- Keep channels long-lived with deterministic names (for example, `source-env-region-partition`); scale out by opening more channels, not by reopening them.
- Advance your source checkpoint only after the committed offset token reaches it.
- Carry `CHANNEL_ID` and a monotonically increasing `STREAM_OFFSET` in each row so you can audit gaps and duplicates in SQL.
- Map columns explicitly instead of ingesting raw VARIANT to cut billed bytes.
- Pass native objects (dicts, lists) for semi-structured fields rather than serialized JSON strings, which are stored as literal text.
- In Java deployments, limit the JVM heap to about half the host memory, because the Rust core allocates outside the heap.

## Common pitfalls

- Treating a successful append call as a commit; durable progress is only the committed offset token.
- Ignoring `row_error_count`, so server-side schema rejections go unnoticed.
- Retrying REST requests immediately without exponential backoff and jitter.
- Assuming classic and high-performance SDKs, channel semantics, and billing are interchangeable.

## Learn more

- [Snowpipe Streaming overview](https://docs.snowflake.com/en/user-guide/snowpipe-streaming/data-load-snowpipe-streaming-overview)
- [Best practices for the high-performance architecture](https://docs.snowflake.com/en/user-guide/snowpipe-streaming/snowpipe-streaming-high-performance-best-practices)
- [High-performance architecture costs](https://docs.snowflake.com/en/user-guide/snowpipe-streaming/snowpipe-streaming-high-performance-cost)

## Knowledge check

### A producer streams verbose JSON events with long key names into a single VARIANT column using the high-performance architecture. Finance asks how to reduce ingestion cost without dropping data. What is the best change?
- [ ] Compress the events with gzip before appending
- [x] Define a pipe that maps fields to typed columns with MATCH_BY_COLUMN_NAME = CASE_SENSITIVE
- [ ] Open and close a new channel for each batch
- [ ] Switch to a larger warehouse
> Billing counts data values, and loading into a single VARIANT bills all JSON bytes including keys. Column mapping bills only the values and is more efficient for the engine.

### After a consumer crash, how should the client decide where to resume reading from the source?
- [ ] Resume from the source's own consumer offset
- [x] Read the channel's latest committed offset token from Snowflake and replay after it
- [ ] Re-send the last hour of data and rely on Snowflake to deduplicate
> Snowflake persists the last committed offset token per channel. Using it as the source of truth gives exactly-once behavior across restarts.

### Append calls succeed, but rows are missing in the table. Where should you look first?
- [x] getChannelStatus, especially row_error_count and the last committed offset
- [ ] LOAD_HISTORY
- [ ] The stage used by the pipe
> Some errors, such as server-side schema validation failures, surface asynchronously after rows are buffered. Channel status reports these errors and shows how far ingestion has committed.
