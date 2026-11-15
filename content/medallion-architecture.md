# Layered (Medallion) Architecture

A layered, or medallion, architecture organizes data into successive zones of increasing quality: raw (bronze) data as it landed, curated (silver) data that is cleaned and conformed, and consumption (gold) data modeled for specific use cases. On Snowflake, the pattern is implemented with databases or schemas, roles, and declarative pipelines, and the main architectural questions concern boundaries, ownership, refresh mechanics, and cost rather than storage engines.

## How it works

**Layers and their contracts**

- **Raw / bronze**: an immutable or append-only record of source data, loaded with COPY, Snowpipe, Snowpipe Streaming, connectors, or shares. Keep the source shape, often with VARIANT for semi-structured payloads, plus load metadata such as file name, load timestamp, and source system. Its purpose is replayability and auditability.
- **Curated / silver**: typed, deduplicated, validated, and conformed entities (customers, orders, events) with consistent keys and history handling such as SCD Type 2. This is the integration layer, and most data quality rules live here.
- **Consumption / gold**: dimensional models, aggregates, feature tables, and semantic views shaped for BI, AI, applications, or sharing. These are the published interfaces.

**Physical layout options**

- One database per layer (`RAW`, `CURATED`, `ANALYTICS`) with a schema per source or domain. Grants are simple, and environments become separate databases or accounts.
- One database per domain with a schema per layer. This aligns with domain ownership and data mesh, and database roles keep access local to the domain.

**Pipeline mechanics**

- **Dynamic tables** are a natural fit for silver and gold: you declare the query and a `TARGET_LAG`, and Snowflake refreshes incrementally where the query allows. Intermediate tables can use `TARGET_LAG = DOWNSTREAM` so that they refresh only when consumers need them. Check the refresh mode actually chosen, because some constructs force full refreshes.
- **Streams and tasks** remain the right tool when you need procedural logic, MERGE semantics with complex rules, or external calls.
- **dbt** (including dbt Projects on Snowflake) is a common way to manage model code, tests, and documentation across layers.

**Storage choices**

- **Transient tables** have no Fail-safe and at most one day of Time Travel. They suit re-creatable staging and intermediate data where reduced storage cost outweighs recoverability. Keep raw history and published gold tables permanent if you cannot cheaply rebuild them.
- A transient schema or database makes every table created in it transient, which is convenient for staging zones.

## Example

Bronze lands JSON. Silver deduplicates and types it with a dynamic table. Gold aggregates for BI:

```sql
CREATE TRANSIENT SCHEMA raw.web;
CREATE TABLE raw.web.events_raw (
  payload   VARIANT,
  file_name STRING,
  loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE DYNAMIC TABLE curated.web.events
  TARGET_LAG = DOWNSTREAM
  WAREHOUSE = transform_wh
AS
SELECT payload:event_id::STRING        AS event_id,
       payload:user_id::NUMBER         AS user_id,
       payload:event_type::STRING      AS event_type,
       payload:ts::TIMESTAMP_NTZ       AS event_ts
FROM raw.web.events_raw
QUALIFY ROW_NUMBER() OVER (PARTITION BY payload:event_id ORDER BY loaded_at DESC) = 1;

CREATE OR REPLACE DYNAMIC TABLE analytics.web.daily_active_users
  TARGET_LAG = '1 hour'
  WAREHOUSE = transform_wh
AS
SELECT DATE_TRUNC('day', event_ts) AS activity_date,
       COUNT(DISTINCT user_id)     AS active_users
FROM curated.web.events
GROUP BY 1;
```

The gold table's one-hour lag drives refresh of the silver table upstream. Because the raw schema is transient, its tables have no Fail-safe, so this choice only makes sense if the source can be reloaded.

## Best practices

- Define explicit contracts per layer: who owns it, which schema or quality guarantees apply, and who may read it. Grant consumers access to gold (and sometimes silver), never to raw by default.
- Make raw replayable: keep source files or retain raw history long enough to rebuild silver after a logic bug.
- Use dynamic tables where the logic is declarative, and tune `TARGET_LAG` to business freshness needs rather than "as fast as possible". Lag drives cost.
- Separate warehouses for ingestion, transformation, and consumption so you can size, attribute, and cap each layer's spend.
- Attach data quality checks (for example data metric functions) at the silver boundary, and fail or quarantine before bad data reaches gold.
- Keep naming consistent across layers so lineage is obvious, for example `raw.<source>`, `curated.<domain>`, and `analytics.<product>`.

## Common pitfalls

- Letting BI tools read bronze or silver directly, which turns internal tables into accidental public interfaces.
- Making everything transient to save storage and then being unable to recover from an accidental delete in a layer that cannot be rebuilt.
- Building a deep chain of dynamic tables with short lags everywhere, which multiplies refresh compute.
- Using non-deterministic or unsupported constructs that silently push dynamic tables to full refresh.
- Copying the medallion pattern by habit and creating many near-duplicate layers that add latency without adding value.

## Learn more

- [Dynamic tables](https://docs.snowflake.com/en/user-guide/dynamic-tables/overview)
- [Working with temporary and transient tables](https://docs.snowflake.com/en/user-guide/tables-temp-transient)

## Knowledge check

### Analysts need hourly freshness on a gold table, and the silver table in between is used by nothing else. How should the silver dynamic table's lag be set?
- [ ] TARGET_LAG = '1 minute' to guarantee freshness
- [x] TARGET_LAG = DOWNSTREAM so it refreshes only as needed to satisfy the gold table's lag
- [ ] Use a task that refreshes it every 5 minutes
- [ ] Make it a view instead of a table in every case
> DOWNSTREAM lets the consumer's lag drive refresh scheduling, avoiding wasted refreshes of intermediate tables.

### A staging zone is fully rebuildable from files kept in cloud storage for 90 days. What storage choice reduces cost with acceptable risk?
- [x] Use a transient schema, accepting no Fail-safe and at most one day of Time Travel
- [ ] Use permanent tables with 90 days of Time Travel
- [ ] Use hybrid tables
- [ ] Use temporary tables that persist across sessions
> Transient objects avoid Fail-safe storage costs. That trade-off is appropriate when the data can be reloaded from source.

### A dashboard team asks for direct access to silver tables because gold is missing one column. What is the best architectural response?
- [ ] Grant SELECT on all silver schemas to the BI role
- [x] Add the column to the gold model (or create a new gold product), keeping gold as the published interface
- [ ] Copy the silver table into the BI tool's extract
- [ ] Give the team ownership of the silver schema
> Gold is the contract for consumers. Extending it preserves layer boundaries, quality guarantees, and the freedom to change silver internals.
