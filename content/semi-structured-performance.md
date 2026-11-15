# Semi-structured Performance

VARIANT columns can perform close to relational columns, or dramatically worse, depending on how the data is shaped. Senior engineers need to understand Snowflake's sub-columnarization of VARIANT data, what defeats it, and when to promote fields into typed columns or use structured types instead.

## How it works

**Sub-columnarization.** When semi-structured data is inserted into a VARIANT column, Snowflake extracts as many elements as possible into an internal columnar form; the rest is stored as a single parsed semi-structured blob. By default, Snowflake extracts at most **200 elements per partition, per table** (raising this requires Snowflake Support).

Extracted elements behave much like real columns: the engine scans only the extracted sub-column, and per-partition metadata supports pruning. Elements that are not extracted force the engine to read the whole document and traverse it for every row.

**What blocks extraction:**

- An element that contains even a single JSON `null` value in the partition. This preserves the distinction between JSON null and SQL NULL. Missing keys are fine; explicit nulls are not.
- An element whose values have **mixed types**, for example `{"foo": 1}` in one row and `{"foo": "1"}` in another.

**Non-native types.** JSON has no date or timestamp type, so such values are stored as strings in VARIANT. Operations on them are slower and use more space than typed columns, and casting a string inside a predicate can weaken pruning compared with a native DATE or TIMESTAMP column. Snowflake specifically recommends flattening into relational columns when data contains dates and timestamps (especially non-ISO 8601), numbers inside strings, and arrays.

**Structured types.** Structured ARRAY, OBJECT, and MAP types (for example `OBJECT(city VARCHAR, zip VARCHAR)` or `ARRAY(NUMBER)`) declare element types. They give schema enforcement and typed elements without fully flattening into separate columns. The trade-off is reduced flexibility: schema drift requires DDL, and some functions require both arguments to be structured or both semi-structured.

**Decision framework:**

| Situation | Recommendation |
| --- | --- |
| Exploration, unknown access paths | Keep VARIANT; profile later |
| Hot filter, join, or clustering keys | Promote to typed columns |
| Dates/timestamps or numbers as strings | Promote and cast at load |
| Stable nested shape needing type guarantees | Structured types |
| Highly variable, rarely queried payload | Keep VARIANT alongside promoted columns |
| Arrays queried per element | Materialize a flattened child table |

## Example

Load with nulls stripped so sparse keys remain extractable:

```sql
CREATE OR REPLACE FILE FORMAT json_ff
  TYPE = JSON
  STRIP_NULL_VALUES = TRUE;

COPY INTO events_raw (v)
  FROM @events_stage
  FILE_FORMAT = (FORMAT_NAME = 'json_ff');
```

Promote hot fields to typed columns during load, keeping the full payload:

```sql
CREATE OR REPLACE TABLE events (
  event_ts   TIMESTAMP_NTZ,
  user_id    NUMBER,
  event_type VARCHAR,
  payload    VARIANT
) CLUSTER BY (TO_DATE(event_ts));

INSERT INTO events
SELECT TRY_TO_TIMESTAMP_NTZ(v:ts::STRING),
       v:user.id::NUMBER,
       v:type::STRING,
       v
FROM events_raw;
```

Use a structured type when the shape is stable:

```sql
CREATE OR REPLACE TABLE customers (
  id      NUMBER,
  address OBJECT(street VARCHAR, city VARCHAR, zip VARCHAR),
  tags    ARRAY(VARCHAR)
);
```

Check type consistency for a key before relying on it:

```sql
SELECT TYPEOF(v:user.id) AS t, COUNT(*)
FROM events_raw
GROUP BY 1;
```

## Best practices

- Normalize types at the producer or in staging so each key holds one native type.
- Use `STRIP_NULL_VALUES = TRUE` when JSON nulls carry no meaning.
- Promote fields used in WHERE, JOIN, GROUP BY, and clustering keys; keep the raw VARIANT for flexibility and reprocessing.
- Compare query profiles (partitions scanned, bytes scanned) on VARIANT versus promoted columns with representative data before committing to a model.
- Watch wide documents: beyond the per-partition extraction limit, less-common keys stay in the blob.

## Common pitfalls

- Producers emitting `"id": 123` and `"id": "123"` interchangeably, silently disabling extraction.
- Filtering on `v:ts::TIMESTAMP` over string timestamps and expecting the same pruning as a native column.
- Flattening arrays at query time in every dashboard instead of materializing once.
- Adopting structured types for volatile schemas and then fighting frequent DDL changes.

## Learn more

- [Considerations for semi-structured data stored in VARIANT](https://docs.snowflake.com/en/user-guide/semistructured-considerations)
- [Structured data types](https://docs.snowflake.com/en/sql-reference/data-types-structured)

## Knowledge check

### Queries filtering on `v:device.region` scan full documents even though the key is present in most rows. Investigation shows some rows contain `"region": null`. What is happening?
- [ ] The key name is too long to extract
- [x] Explicit JSON null values prevent the element from being extracted into a sub-column
- [ ] VARIANT columns never support pruning
- [ ] The table needs search optimization to be enabled
> An element containing even one JSON null in a partition is not extracted, forcing full document traversal; stripping nulls or promoting the field fixes it.

### An events table stores ISO timestamps as strings in VARIANT and most queries filter on time ranges. What design is best?
- [ ] Keep VARIANT and cast in every query
- [x] Promote the timestamp to a typed TIMESTAMP column at load and cluster or filter on it
- [ ] Convert the whole payload to a structured OBJECT
- [ ] Store timestamps as numbers inside strings
> Dates and timestamps are stored as strings in VARIANT; a native typed column gives better pruning and less storage.

### When are structured types a better fit than plain VARIANT?
- [ ] When the schema changes daily with new keys
- [x] When the nested shape is stable and you want declared element types
- [ ] When loading arbitrary third-party JSON for exploration
- [ ] When you need to mix types within one key
> Structured types enforce element types for a known, stable shape, at the cost of flexibility when the schema drifts.
