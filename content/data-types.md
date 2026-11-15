# Data Types

Every column, variable, and expression in Snowflake has a data type. The type determines what values the column can hold and how they are stored and compared. Snowflake supports standard SQL types plus native types for semi-structured, geospatial, and vector data. Choosing the right type keeps data correct and queries predictable.

## How it works

The main categories are:

- **Numeric**
  - `NUMBER(p, s)` stores exact fixed-point values. Precision can be up to 38 digits. `INT`, `INTEGER`, `BIGINT`, and `DECIMAL` are synonyms for NUMBER (integer synonyms have a scale of 0).
  - **Storage vs. Precision:** Declaring a large precision (e.g. `NUMBER(38,0)`) does **not** consume extra storage because micro-partitions dynamically bit-pack to the actual minimum and maximum values stored. However, scale ($s$, digits following the decimal point) **does** impact storage and compression.
  - `FLOAT` (also `DOUBLE`, `REAL`) stores approximate floating-point values, including special values such as `'NaN'`.
- **String and binary**
  - `VARCHAR` (also `STRING`, `TEXT`) stores Unicode text in UTF-8. When no length is given, the default maximum is 16 MB. A short string uses only the space it needs, so declaring `VARCHAR` without length does not waste storage. `CHAR` is a VARCHAR with a default length of 1.
  - **Delimiters:** String literals can be enclosed in single quotes (`'text'`) or double dollar signs (`$$text with 'quote'$$`), useful for multi-line strings without escaping single quotes.
  - `BINARY` stores raw bytes. The default maximum is 8 MB.
- **Logical:** `BOOLEAN` holds TRUE, FALSE, or NULL.
- **Date, time, and intervals**
  - `DATE` stores only a calendar date.
  - `TIME` stores a time of day with fractional precision from 0 to 9 (default is 9 nanoseconds).
  - `TIMESTAMP_NTZ` stores a timestamp without a time zone ("wall clock").
  - `TIMESTAMP_LTZ` stores a UTC instant and shows it in the session time zone.
  - `TIMESTAMP_TZ` stores a timestamp with its own time zone offset.
  - Plain `TIMESTAMP` maps to one of the three variants above, according to the `TIMESTAMP_TYPE_MAPPING` parameter.
  - **Interval Arithmetic Quirk:** The order of interval addition matters across leap years: `SELECT TO_DATE('2019-02-28') + INTERVAL '1 day, 1 year'` evaluates to `2020-03-01`, whereas `+ INTERVAL '1 year, 1 day'` evaluates to `2020-02-29`.
- **Semi-structured**
  - `VARIANT` holds any value, including JSON-like nested data.
  - `OBJECT` holds key-value pairs.
  - `ARRAY` holds ordered lists.
  - You navigate nested values with `:` and `.` notation, and cast them with `::`.
- **Geospatial:** `GEOGRAPHY` (earth coordinates) and `GEOMETRY` (planar coordinates).
- **Vector:** `VECTOR` for embeddings used in similarity search and AI workloads.

**Conversion.** Use `CAST(x AS type)` or `x::type`. Functions such as `TRY_CAST` and `TRY_TO_NUMBER` return NULL instead of an error when a value cannot be converted, which is useful for messy input.

## Example

A table that uses several data types, followed by a query that reads JSON fields:

```sql
CREATE OR REPLACE TABLE events (
  event_id   NUMBER(38,0),
  user_email VARCHAR,
  amount     NUMBER(12,2),
  is_test    BOOLEAN,
  event_ts   TIMESTAMP_LTZ,
  payload    VARIANT
);

INSERT INTO events
SELECT 1, 'ana@example.com', 19.99, FALSE, CURRENT_TIMESTAMP(),
       PARSE_JSON('{"device": {"os": "ios"}, "items": [101, 202]}');

SELECT payload:device.os::STRING   AS os,
       payload:items[0]::NUMBER    AS first_item,
       TRY_CAST('abc' AS NUMBER)   AS safe_cast   -- returns NULL
FROM events;
```

`PARSE_JSON` is used in a `SELECT` rather than a `VALUES` clause, because that is where it is supported for inserts.

## Best practices

- Use `NUMBER` with an explicit scale for money. Avoid FLOAT for values that must be exact.
- Pick one timestamp approach and use it everywhere. `TIMESTAMP_NTZ` stored in UTC, or `TIMESTAMP_LTZ`, are common choices.
- Land raw JSON in VARIANT, then move frequently queried fields into typed columns.
- Use `TRY_` functions when cleaning unreliable source data.

## Common pitfalls

- Using FLOAT for currency and getting rounding errors.
- Mixing `TIMESTAMP_NTZ` and `TIMESTAMP_LTZ`, which shifts times when session time zones differ.
- Forgetting to cast VARIANT values (for example `::STRING`). Without the cast, results keep JSON quoting and comparisons can behave unexpectedly.
- Assuming `VARCHAR(10)` is faster or smaller than `VARCHAR`. The length is only a constraint.

## Learn more

- [Summary of data types](https://docs.snowflake.com/en/sql-reference/intro-summary-data-types)
- [String & binary data types](https://docs.snowflake.com/en/sql-reference/data-types-text)

## Knowledge check

### Which type should store invoice amounts such as 1234.56 exactly?
- [ ] FLOAT
- [x] NUMBER(12,2)
- [ ] VARCHAR
- [ ] VARIANT
> NUMBER is exact fixed-point. FLOAT is approximate and can introduce rounding errors.

### A source sends a numeric field that sometimes contains text like "N/A". How can you load it without the query failing?
- [ ] CAST the value to NUMBER
- [x] Use TRY_CAST or TRY_TO_NUMBER, which return NULL for invalid values
- [ ] Store it as BOOLEAN
- [ ] Use FLOAT instead
> TRY_ conversion functions return NULL instead of raising an error when conversion fails.

### A column is declared as plain `VARCHAR` and holds mostly 5-character codes. What is the storage impact?
- [ ] Each value uses the full 16 MB maximum
- [x] Each value uses only the space it needs; the length is just a maximum
- [ ] The column is converted to CHAR(5)
- [ ] Storage doubles compared to VARCHAR(5)
> VARCHAR storage depends on the actual data, so a large declared maximum does not waste space.
