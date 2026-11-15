# Upsert changes from a stream with MERGE

topics: streams, pipeline-design
tags: cdc, merge, sql
level: intermediate

A standard stream records inserts, updates, and deletes on a source table. An update appears as a DELETE plus an INSERT pair with `METADATA$ISUPDATE = TRUE`; this MERGE applies the net change to a target table.

```sql
USE SCHEMA my_db.silver;

CREATE OR REPLACE STREAM customers_stream ON TABLE my_db.bronze.customers;

MERGE INTO my_db.silver.customers AS t
USING (
  -- Drop the DELETE half of updates; keep inserts, updates (as INSERT rows), and real deletes
  SELECT *
  FROM customers_stream
  WHERE NOT (METADATA$ACTION = 'DELETE' AND METADATA$ISUPDATE)
  -- If the source could change a key several times between runs, keep one row per key
  QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1
) AS s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.METADATA$ACTION = 'DELETE' THEN
  DELETE
WHEN MATCHED AND s.METADATA$ACTION = 'INSERT' THEN
  UPDATE SET t.name = s.name,
             t.email = s.email,
             t.updated_at = s.updated_at
WHEN NOT MATCHED AND s.METADATA$ACTION = 'INSERT' THEN
  INSERT (customer_id, name, email, updated_at)
  VALUES (s.customer_id, s.name, s.email, s.updated_at);

-- The stream offset advances only when the DML commits
SELECT SYSTEM$STREAM_HAS_DATA('customers_stream');
```

## Notes
- A standard stream already returns the net change per row since the last offset; the `QUALIFY` guards against duplicate keys in the source table itself.
- Run the MERGE inside a task (for example a triggered task) so changes are applied continuously.
- If the stream isn't consumed within the table's data retention period (extended up to `MAX_DATA_EXTENSION_TIME_IN_DAYS`), it becomes stale and must be recreated.

## References
- [Introduction to streams](https://docs.snowflake.com/en/user-guide/streams-intro)
- [MERGE](https://docs.snowflake.com/en/sql-reference/sql/merge)
- [CREATE STREAM](https://docs.snowflake.com/en/sql-reference/sql/create-stream)
