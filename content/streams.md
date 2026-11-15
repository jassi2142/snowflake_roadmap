# Streams (CDC)

A stream is a Snowflake object that records the row-level changes (inserts, updates, and deletes) made to a source object since a point in time, a pattern known as change data capture (CDC). Streams let a pipeline process only what changed instead of rescanning whole tables, which makes incremental loads cheaper and simpler.

## How it works

A stream does not store table data. It stores an **offset**: a pointer between two committed versions of the source object. When you query the stream, Snowflake uses the source's versioning history plus hidden change-tracking columns (added to the table when the first stream is created) to return the minimal set of changes between the offset and the current version.

Each row returned has the source columns plus three metadata columns:

- `METADATA$ACTION`: `INSERT` or `DELETE`.
- `METADATA$ISUPDATE`: `TRUE` when the row is half of an update. Updates appear as a DELETE/INSERT pair.
- `METADATA$ROW_ID`: a unique, immutable ID for the row.

Key behaviors:

- **Selecting from a stream does not consume it.** The offset advances only when the stream is read inside a DML statement (INSERT, MERGE, CTAS, COPY INTO location) that commits successfully.
- Streams support **repeatable read**: within an explicit transaction (`BEGIN ... COMMIT`), every statement sees the same change set, so several statements can consume the same delta.
- **Stream types**: *standard* (all DML, net delta), *append-only* (inserts only; cheaper for ELT on insert-heavy tables), and *insert-only* (for external tables and externally managed Iceberg tables).
- Sources include standard tables, views (including secure views), directory tables, dynamic tables, event tables, external tables, and Iceberg tables (with limitations). Streams on views require change tracking on the view and its underlying tables, and the view can only use projections, filters, inner/cross joins, and UNION ALL.

**Staleness.** A stream becomes stale when its offset falls outside the source table's data retention period. If retention is under 14 days and the stream is unconsumed, Snowflake temporarily extends retention up to `MAX_DATA_EXTENSION_TIME_IN_DAYS` (14 days by default, regardless of edition). `SHOW STREAMS` and `DESCRIBE STREAM` report a `STALE_AFTER` timestamp. A stale stream must be recreated. Recreating the source table with `CREATE OR REPLACE` also makes its streams stale.

## Example

Create a stream on a raw table and merge its changes into a target table. The MERGE consumes the stream and advances the offset.

```sql
CREATE OR REPLACE STREAM raw_orders_stream ON TABLE raw_orders;

MERGE INTO orders t
USING (
  SELECT * FROM raw_orders_stream
  WHERE NOT (METADATA$ACTION = 'DELETE' AND METADATA$ISUPDATE)
) s
ON t.order_id = s.order_id
WHEN MATCHED AND s.METADATA$ACTION = 'DELETE' THEN DELETE
WHEN MATCHED THEN UPDATE SET t.status = s.status, t.amount = s.amount
WHEN NOT MATCHED AND s.METADATA$ACTION = 'INSERT' THEN
  INSERT (order_id, status, amount) VALUES (s.order_id, s.status, s.amount);
```

The filter drops the DELETE half of each update so every key appears once. Check staleness with:

```sql
SHOW STREAMS LIKE 'raw_orders_stream';
```

## Best practices

- Create **one stream per consumer**. Two consumers sharing one stream will each see a different delta.
- Use **append-only** streams for insert-only staging tables; they are more performant than standard streams.
- Pair streams with tasks using `WHEN SYSTEM$STREAM_HAS_DATA('stream_name')` so runs are skipped when nothing changed.
- Consume streams more often than the source table's retention period, and monitor `STALE_AFTER`.
- Use the `CHANGES` clause instead of a stream when you need read-only access to changes between arbitrary points in time without managing an offset.

## Common pitfalls

- Expecting a plain `SELECT` to advance the offset. Only committed DML consumes a stream.
- Running `CREATE OR REPLACE TABLE` on the source, which drops its history and makes all streams on it stale.
- Forgetting that an update produces two rows, which leads to duplicate-key errors in MERGE.
- Adding a NOT NULL constraint to a column, after which stream queries can fail if historical change rows contain NULLs.

## Learn more

- [Introduction to streams](https://docs.snowflake.com/en/user-guide/streams-intro)
- [Manage streams](https://docs.snowflake.com/en/user-guide/streams-manage)

## Knowledge check

### An analyst runs `SELECT * FROM orders_stream` three times and gets the same rows each time. Why?
- [ ] The stream is stale and returns cached results
- [x] Querying a stream outside a DML statement does not advance its offset
- [ ] Streams only refresh once per hour
- [ ] The analyst's role lacks the privilege to consume the stream
> The offset advances only when the stream is used in a DML transaction that commits; a plain SELECT leaves the change set in place.

### Two separate tasks need to process every change to the same table independently. What is the recommended design?
- [ ] Both tasks read the same stream inside one explicit transaction
- [ ] Use one append-only stream and have the second task use Time Travel
- [x] Create a separate stream for each task
- [ ] Enable change tracking twice on the table
> Each consumer that advances an offset needs its own stream; streams store only an offset, so extra streams are cheap.

### A table has `DATA_RETENTION_TIME_IN_DAYS = 1` and its stream was not consumed for several days, yet it is still readable. What explains this?
- [ ] Streams store a full copy of changed rows
- [ ] Streams never go stale on standard tables
- [x] Snowflake temporarily extends retention for unconsumed streams, up to MAX_DATA_EXTENSION_TIME_IN_DAYS (14 days by default)
- [ ] Fail-safe keeps the change data accessible to streams
> When retention is under 14 days, Snowflake extends it for an unconsumed stream up to the MAX_DATA_EXTENSION_TIME_IN_DAYS limit, after which the stream can become stale.
