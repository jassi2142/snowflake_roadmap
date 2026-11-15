# Logging & Tracing (event tables)

Snowflake's telemetry model collects logs, trace events and metrics from stored procedures, UDFs, services and Snowflake features into an **event table**, a special table with a predefined, OpenTelemetry-aligned schema. For engineers running production pipelines and applications on Snowflake, event tables replace ad hoc "log to a table" patterns with a consistent, queryable and governable observability layer.

## How it works

**The event table.** Snowflake provides a default event table, `SNOWFLAKE.TELEMETRY.EVENTS`, which is active unless you set another one, plus a view `SNOWFLAKE.TELEMETRY.EVENTS_VIEW` for safer sharing. You can create your own with `CREATE EVENT TABLE` (no column list; the schema is fixed) and associate it with the **account** or a **database** through the `EVENT_TABLE` parameter. A database-level association takes precedence over the account-level one and is an Enterprise Edition feature. Event tables are not replicated.

**Schema essentials.** Important columns include `TIMESTAMP` (UTC), `RECORD_TYPE` (for example `LOG`, `SPAN`, `SPAN_EVENT`, `EVENT`, `METRIC`), `RECORD` (severity, span name and similar), `VALUE` (the message or measurement), `RESOURCE_ATTRIBUTES` (which database, schema, object, warehouse and query produced it) and `RECORD_ATTRIBUTES`. Most fields are semi-structured, so queries use path notation.

**Telemetry levels decide what is captured.** Nothing is collected unless the relevant level allows it:

- `LOG_LEVEL` for messages emitted through logging APIs (TRACE, DEBUG, INFO, WARN, ERROR, FATAL, OFF).
- `TRACE_LEVEL` for spans (`ALWAYS`, `ON_EVENT`, `OFF`). `ON_EVENT` records trace data only when your code explicitly emits events.
- `METRIC_LEVEL` for resource metrics (`ALL` or `NONE`).
- `LOG_EVENT_LEVEL` for events emitted by Snowflake features such as Snowpipe.

Levels resolve through two hierarchies: **Account » Database » Schema » Object** for object parameters and **Account » User » Session** for session parameters. The lower level overrides the higher, and when both a session value and an object value apply, the **more verbose** level wins. This lets you keep production quiet at the account level while turning on DEBUG for one procedure, or for one developer's session.

**Emitting data.** Handler code uses language-native APIs: the Python `logging` module, Java and Scala loggers, JavaScript `snowflake.log`, and `SYSTEM$LOG_*` functions in Snowflake Scripting. Traces can be enriched with custom span events and attributes.

**Access control.** The application roles `SNOWFLAKE.EVENTS_VIEWER` (SELECT on EVENTS_VIEW) and `SNOWFLAKE.EVENTS_ADMIN` (SELECT, TRUNCATE and DELETE on the default event table) govern the default table. Row access policies on EVENTS_VIEW let you restrict rows by team; that is an Enterprise Edition feature.

**Cost.** Collecting telemetry incurs cost, so verbosity is a design decision. Very verbose levels on high-volume objects generate significant ingestion; DEBUG and TRACE belong on narrowly scoped objects or sessions.

## Example

Create a dedicated event table for a product database and set a quiet default with a verbose override:

```sql
CREATE EVENT TABLE observability.telemetry.app_events;
ALTER DATABASE app_db SET EVENT_TABLE = observability.telemetry.app_events;

ALTER DATABASE app_db SET LOG_LEVEL = WARN;
ALTER PROCEDURE app_db.etl.load_orders(VARCHAR) SET LOG_LEVEL = DEBUG;
ALTER PROCEDURE app_db.etl.load_orders(VARCHAR) SET TRACE_LEVEL = ON_EVENT;
```

Emit logs from Snowflake Scripting:

```sql
CREATE OR REPLACE PROCEDURE app_db.etl.load_orders(batch_id VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
  SYSTEM$LOG_INFO('Starting batch ' || :batch_id);
  -- ... load logic ...
  RETURN 'ok';
EXCEPTION
  WHEN OTHER THEN
    SYSTEM$LOG_ERROR('Batch ' || :batch_id || ' failed: ' || SQLERRM);
    RAISE;
END;
$$;
```

Query recent errors with their originating object:

```sql
SELECT timestamp,
       resource_attributes:"snow.executable.name"::STRING AS executable,
       record:"severity_text"::STRING                     AS severity,
       value::STRING                                      AS message
FROM observability.telemetry.app_events
WHERE record_type = 'LOG'
  AND record:"severity_text"::STRING IN ('ERROR', 'FATAL')
  AND timestamp >= DATEADD('hour', -24, SYSDATE())
ORDER BY timestamp DESC;
```

Because `TIMESTAMP` is UTC, compare it with `SYSDATE()` rather than `CURRENT_TIMESTAMP()`.

## Best practices

- Set conservative account-level defaults and raise verbosity only on specific objects or sessions.
- Use separate event tables per domain when teams need isolation, cost visibility or different retention.
- Pair event tables with **alerts on new data** for near-real-time error notification.
- Build views on top of the event table that flatten common attributes for analysts.
- Purge or archive old telemetry deliberately; event tables accumulate quickly.

## Common pitfalls

- Expecting logs to appear without setting LOG_LEVEL; the default level means nothing from your code is captured.
- Leaving DEBUG on at the account level and paying to ingest large volumes of telemetry.
- Comparing the UTC `TIMESTAMP` column with local-time functions and querying the wrong window.
- Assuming event tables replicate to a secondary account for disaster recovery.
- Granting broad SELECT on the raw event table when EVENTS_VIEW with a row access policy would limit exposure.

## Learn more

- [Event table overview](https://docs.snowflake.com/en/developer-guide/logging-tracing/event-table-setting-up)
- [Setting levels for logging, metrics, and tracing](https://docs.snowflake.com/en/developer-guide/logging-tracing/telemetry-levels)
- [Tutorial: Get started with logging and tracing](https://docs.snowflake.com/en/developer-guide/logging-tracing/tutorials/logging-tracing-getting-started)

## Knowledge check

### The account LOG_LEVEL is ERROR. A developer sets LOG_LEVEL = DEBUG for their session while calling a procedure whose object LOG_LEVEL is WARN. Which level applies?
- [ ] ERROR, because account settings always win
- [ ] WARN, because object settings override sessions
- [x] DEBUG, because when both session and object levels apply the more verbose level is used
- [ ] OFF, because conflicting levels disable logging
> Snowflake uses the most verbose level when both session and object hierarchies set a value, which enables targeted debugging without changing production defaults.

### A platform team wants product A's telemetry isolated from product B's, with separate access control. What design fits best?
- [ ] Keep everything in SNOWFLAKE.TELEMETRY.EVENTS and filter by name
- [x] Create an event table per product and associate each with that product's database through the EVENT_TABLE parameter
- [ ] Set TRACE_LEVEL = OFF for product B
- [ ] Replicate the default event table into two accounts
> Database-level event table association routes each database's telemetry into its own table, which can be secured and costed independently; it takes precedence over the account-level table.

### Ingestion costs for telemetry rose sharply after a release. What is the most likely cause?
- [ ] The event table was not clustered
- [x] A verbose level such as DEBUG or TRACE_LEVEL = ALWAYS was set broadly on high-volume objects
- [ ] EVENTS_VIEW was queried too often
- [ ] The event table was associated with a database instead of the account
> Telemetry collection incurs cost proportional to what is captured; broadly verbose levels on busy objects are the usual driver.
