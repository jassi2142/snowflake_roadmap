# Slowly changing dimension Type 2 with a stream and MERGE

topics: streams, medallion-architecture
tags: cdc, merge, scd2, sql
level: advanced

Keep full history of a dimension: when a tracked attribute changes, close the current row and insert a new current version. A single MERGE does both by feeding each changed key twice: once to close and once to insert.

```sql
USE SCHEMA my_db.gold;

CREATE TABLE IF NOT EXISTS my_db.gold.dim_customer (
  customer_id  NUMBER,
  name         STRING,
  city         STRING,
  valid_from   TIMESTAMP_NTZ,
  valid_to     TIMESTAMP_NTZ,
  is_current   BOOLEAN
);

CREATE OR REPLACE STREAM customer_changes ON TABLE my_db.silver.customers;

MERGE INTO my_db.gold.dim_customer AS d
USING (
  WITH changes AS (
    SELECT customer_id, name, city, updated_at
    FROM customer_changes
    WHERE METADATA$ACTION = 'INSERT'          -- new rows and new side of updates
  )
  -- Row 1 per key: matches the current version (to close it)
  SELECT customer_id AS merge_key, customer_id, name, city, updated_at FROM changes
  UNION ALL
  -- Row 2 per key: NULL key never matches, so it is inserted as the new version
  SELECT NULL AS merge_key, c.customer_id, c.name, c.city, c.updated_at
  FROM changes c
  JOIN my_db.gold.dim_customer d
    ON d.customer_id = c.customer_id AND d.is_current
  WHERE d.name IS DISTINCT FROM c.name OR d.city IS DISTINCT FROM c.city
) AS s
ON d.customer_id = s.merge_key AND d.is_current
WHEN MATCHED AND (d.name IS DISTINCT FROM s.name OR d.city IS DISTINCT FROM s.city) THEN
  UPDATE SET d.valid_to = s.updated_at, d.is_current = FALSE
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, city, valid_from, valid_to, is_current)
  VALUES (s.customer_id, s.name, s.city, s.updated_at, NULL, TRUE);

-- Current view of the dimension
SELECT * FROM my_db.gold.dim_customer WHERE is_current;
```

## Notes
- Brand-new customers have no current row, so their row 1 does not match and is inserted; row 2 is not produced for them.
- Unchanged updates (same tracked values) match but fail the change condition, so nothing happens.
- This assumes one change per key per run; deduplicate the stream with `QUALIFY ROW_NUMBER()` first if not. Deletes are ignored here; handle them by closing the current row if your model needs it.

## References
- [Introduction to streams](https://docs.snowflake.com/en/user-guide/streams-intro)
- [MERGE](https://docs.snowflake.com/en/sql-reference/sql/merge)
- [IS [ NOT ] DISTINCT FROM](https://docs.snowflake.com/en/sql-reference/functions/is-distinct-from)
