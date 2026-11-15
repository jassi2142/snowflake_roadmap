# Kafka Connector

The Snowflake Connector for Kafka is a Kafka Connect sink that reads topics and writes their records into Snowflake tables. It is the standard way to land Kafka data in Snowflake without writing custom consumers, and choosing the right connector version and ingestion mode is a significant architecture decision for latency, cost, failover, and exactly-once guarantees.

## How it works

The connector runs inside your Kafka Connect cluster (Apache Kafka or Confluent). There are two generations to understand:

- **Version 4 (v4)**: natively uses the Snowpipe Streaming **high-performance architecture**. Snowflake recommends v4 for new implementations. Data enters each table through a PIPE object, either a Snowflake-managed **default pipe** (which you cannot drop, replace, or modify) or a **user-defined pipe** that you create to apply transformations. Channels are scoped to the pipe.
- **Version 3 and earlier**: supports two ingestion methods, selected with `snowflake.ingestion.method`: `SNOWPIPE` (the default, which buffers records into files and loads them with Snowpipe) or `SNOWPIPE_STREAMING` (Snowpipe Streaming classic, available from version 2.0.0). Classic tuning relies on buffer properties such as `buffer.flush.time` (default 10 seconds), `buffer.count.records` (default 10,000), `buffer.size.bytes` (default 20 MB), and `snowflake.streaming.max.client.lag`.

**Exactly-once delivery** in streaming modes comes from a one-to-one mapping between Kafka partitions and Snowflake channels, plus two offsets: the Kafka consumer offset and the Snowflake **offset token**, which records what has been committed in Snowflake. When a channel opens, the connector treats the committed offset token as the source of truth and resets the consumer offset to match. This means resetting the consumer group offset in Kafka alone does not cause reingestion. To deliberately reprocess, you stop the connector and either drop the channel (so Kafka becomes the source of truth) or open it with a new offset token; for user-defined pipes, recreating the pipe drops its channels.

The connector expects sequentially increasing offsets; Snowflake recommends tombstone records rather than NULL records, because missing offsets can break specific use cases.

**Error handling** uses standard Kafka Connect settings: `errors.tolerance` (`none` by default, or `all`), `errors.log.enable`, and `errors.deadletterqueue.topic.name` for records that cannot be ingested.

**Replication and failover**: Snowflake supports replication and failover for Snowpipe Streaming with the Kafka connector, but not for the file-based Snowpipe mode.

## Example

A minimal v3 properties file using Snowpipe Streaming classic with a dead-letter queue.

```properties
name=orders_sink
connector.class=com.snowflake.kafka.connector.SnowflakeSinkConnector
topics=orders
snowflake.url.name=myorg-myaccount.snowflakecomputing.com:443
snowflake.user.name=KAFKA_SVC
snowflake.private.key=<private-key>
snowflake.role.name=KAFKA_INGEST
snowflake.database.name=RAW
snowflake.schema.name=KAFKA
snowflake.ingestion.method=SNOWPIPE_STREAMING
errors.tolerance=all
errors.log.enable=true
errors.deadletterqueue.topic.name=orders_dlq
```

With v4, inspect channels and committed offsets for a pipe from SQL.

```sql
SHOW PIPES LIKE 'ORDERS' IN SCHEMA raw.kafka;
SHOW CHANNELS IN PIPE "ORDERS";
```

## Best practices

- Choose v4 for new pipelines; plan a migration path for v3 workloads rather than mixing models in one design.
- Use a user-defined pipe when you need typed columns or transformations; it also gives you more recovery options than a default pipe.
- Use key-pair authentication for the connector's service user and a dedicated, least-privilege role.
- Configure a dead-letter queue so poison messages do not stall a partition or get silently dropped.
- Treat offset-token resets as change-managed operations; they can cause duplicates or gaps.
- For classic high-throughput connectors, review `enable.streaming.client.optimization`, which Snowflake suggests disabling at high throughput.

## Common pitfalls

- Resetting the Kafka consumer group and expecting reingestion, while the connector keeps resuming from Snowflake's offset token.
- Recreating a topic (offsets restart at 0) while the channel still holds a high offset token, causing records to be skipped.
- Choosing file-based `SNOWPIPE` mode for a pipeline that needs cross-region failover.
- Sending NULL records that create offset gaps.

## Learn more

- [Snowflake Connector for Kafka](https://docs.snowflake.com/en/user-guide/kafka-connector)
- [Kafka connector with Snowpipe Streaming classic](https://docs.snowflake.com/en/user-guide/snowpipe-streaming/snowpipe-streaming-classic-kafka)

## Knowledge check

### A Kafka topic was deleted and recreated, so offsets restart at 0. The v4 connector logs that it is skipping records because it expects offset 499. What is the recommended way to resume from the start of the new topic?
- [ ] Reset the Kafka consumer group offset to earliest
- [x] Stop the connector, drop the channel so it is recreated with no offset token, then restart
- [ ] Set errors.tolerance=all
- [ ] Truncate the target table
> The connector treats Snowflake's committed offset token as the source of truth. Dropping the channel lets the connector recreate it and use Kafka's offsets as the starting point.

### Your architecture review requires Kafka ingestion to continue after a regional failover to a secondary Snowflake account. Which mode supports this?
- [ ] File-based Snowpipe mode
- [x] Snowpipe Streaming with the Kafka connector
- [ ] Either mode, with no difference
> Snowflake supports replication and failover for Snowpipe Streaming with the Kafka connector, but not for Snowpipe with the Kafka connector.

### How does the connector achieve exactly-once delivery in streaming modes?
- [ ] By deduplicating rows in the target table after loading
- [ ] By committing Kafka consumer offsets before writing to Snowflake
- [x] By mapping each partition to one channel and using Snowflake's committed offset token to reposition the consumer
> Each partition writes through its own channel. On open, the committed offset token tells the connector exactly where to resume, so records are neither lost nor duplicated.
